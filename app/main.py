from fastapi import FastAPI, Form, UploadFile, Request, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routes.auth import router as auth_router
from app.routes.guardar import router as guardar_router
from app.routes.guardar_imagen import router as guardar_imagen_router
from app.routes.historial import router as historial_router
from app.routes.exportar_pdf import router as pdf_router
from app.routes import procesar_imagen
from app.routes.procesar_video import procesar_video
from io import BytesIO
from PIL import Image
import numpy as np
import uuid
import cv2

from app.services.s3_utils import s3, BUCKET_NAME 

import tensorflow as tf
import os
import json
import boto3
import time
from datetime import datetime
from dotenv import load_dotenv
from botocore.exceptions import NoCredentialsError
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
VIDEOS_PREFIX = "videos"
FOTOS_PREFIX  = "fotos"
BUCKET_NAME = os.getenv("BUCKET_NAME")
RUTA_VIDEOS = "videos"

# === Cargar variables de entorno ===
load_dotenv()

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
app.templates = templates 

modelo = tf.keras.models.load_model(Path(__file__).resolve().parent / "models" / "modelo_final.h5")
emociones = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not request.cookies.get("usuario_id"):
        return RedirectResponse("/login")
    email = request.cookies.get("email")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "email": email,
        "emociones_detectadas": None,
        "nombre": "",
        "edad": "",
        "video_nombre": ""
    })

@app.get("/analizar-video/{nombre_video}")
async def analizar_video(nombre_video: str):
    ruta = os.path.join(RUTA_VIDEOS, nombre_video)
    if not os.path.exists(ruta):
        return {"error": "Video no encontrado"}

    resultados = procesar_video(ruta, modelo, emociones)
    return {
        "video": nombre_video,
        "emociones_detectadas": resultados
    }


@app.post("/subir", response_class=HTMLResponse)
async def subir(
    request: Request,
    archivo: UploadFile = File(...),
    nombre: str = Form(...),
    edad: str = Form(...)
):
    
    # Validar sesión
    if not request.cookies.get("usuario_id"):
        return RedirectResponse("/login")
    
    email = request.cookies.get("email")
    content_type = (archivo.content_type or "").lower()

    # ____ suba .mp4 ____
    if content_type.startswith("video/"):
        video_key = f"{VIDEOS_PREFIX}/{archivo.filename}"
        try:
            s3.upload_fileobj(archivo.file, BUCKET_NAME, video_key)
        except Exception as e:
            return HTMLResponse(content=f"Error al subir video a S3: {e}", status_code=500)

        ruta_local = f"temp_{archivo.filename}"
        try:
            s3.download_file(BUCKET_NAME, video_key, ruta_local)
            res = procesar_video(ruta_local, modelo, emociones)
            inicio_det = res.get("inicio_det", "")
            fin_det    = res.get("fin_det", "")
            tiempo_procesamiento = res.get("tiempo_procesamiento")
            os.remove(ruta_local)
        except Exception as e:
            return HTMLResponse(content=f"Error al procesar el video: {e}", status_code=500)

        if not res:
            return templates.TemplateResponse("index.html", {
                "request": request,
                "email": email,
                "mensaje_error": "No se detectaron rostros en el video. Intenta con otro video.",
                "emociones_detectadas": None,
                "nombre": nombre,
                "edad": edad,
                "video_nombre": archivo.filename
            })

        if isinstance(res, dict):
            emociones_list = res.get("resultados", [])
        else:
            emociones_list = res  # ya es una lista
        
        # Si no se detectaron emociones
        if not emociones_list:
            return templates.TemplateResponse("index.html", {
                "request": request,
                "email": email,
                "mensaje_error": "No se detectaron emociones en el video procesado.",
                "emociones_detectadas": None,
                "nombre": nombre,
                "edad": edad,
                "video_nombre": archivo.filename
            })
        
        # Si no se detectaron rostros
        if res is None:
            return templates.TemplateResponse("index.html", {
                "request": request,
                "email": email,
                "mensaje_error": "No se detectaron rostros en el video. Intenta con otro video.",
                "emociones_detectadas": None,
                "nombre": nombre,
                "edad": edad,
                "video_nombre": archivo.filename
            })  

        # === 3. Renderizar resultados ===
        return templates.TemplateResponse("index.html", {
            "request": request,
            "email": email,
            "emociones_detectadas": json.dumps(emociones_list),
            "nombre": nombre,
            "edad": edad,
            "video_nombre": archivo.filename,
            "inicio_det": inicio_det,
            "fin_det": fin_det,
            "tiempo_procesamiento": tiempo_procesamiento
        })

    # ----- CASO IMAGEN -----
    elif content_type.startswith("image/"):
        try:
            raw = await archivo.read()
            img_pil = Image.open(BytesIO(raw)).convert("RGB")

            gray = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2GRAY)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
            if len(faces) == 0:
                return templates.TemplateResponse("index.html", {
                    "request": request,
                    "email": email,
                    "mensaje_error": "No se detectó un rostro en la imagen. Intenta con otra imagen.",
                    "emociones_detectadas": None,
                    "nombre": nombre,
                    "edad": edad,
                    "video_nombre": ""
                })

            img_array = np.array(img_pil.resize((224, 224))).astype("float32") / 255.0
            img_array = img_array.reshape(1, 224, 224, 3)

            import time as _time
            t0 = _time.time()
            pred = modelo.predict(img_array, verbose=0)
            t1 = _time.time()

            emocion_idx = int(np.argmax(pred[0]))
            emocion = emociones[emocion_idx]
            confianza = float(pred[0][emocion_idx]) * 100.0

            inicio_det = round(t0, 2)
            fin_det = round(t1, 2)
            tiempo_procesamiento = round(fin_det - inicio_det, 2)


            safe_name = nombre.strip().replace(" ", "_")
            filename = f"{safe_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"

            foto_key = f"{FOTOS_PREFIX}/{filename}"
            s3.upload_fileobj(BytesIO(raw), BUCKET_NAME, foto_key)

            imagen_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': BUCKET_NAME, 'Key': foto_key},
                ExpiresIn=3600
            )

            res_img = {
            "emocion": emocion,
            "confianza": f"{confianza:.2f}",
            "tiempo": tiempo_procesamiento,
            "imagen_guardada": foto_key,   
            "imagen_url": imagen_url,       
            "nombre": nombre,
            "edad": edad
            }

            return templates.TemplateResponse("index.html", {
                "request": request,
                "email": email,
                "resultado_imagen": res_img,
                "resultado_imagen_json": json.dumps(res_img),  

                "emociones_detectadas": None,
                "video_nombre": ""
            })

        except Exception as e:
            return HTMLResponse(content=f"Error al procesar la imagen: {e}", status_code=500)

    else:
        return HTMLResponse(content="Tipo de archivo no soportado. Sube una imagen o un video.", status_code=400)

@app.get("/protegido")
async def protegido(request: Request):
    if not request.cookies.get("usuario_id"):
        return RedirectResponse("/login")
    return HTMLResponse("Contenido privado")


app.include_router(auth_router)
app.include_router(guardar_router)
app.include_router(guardar_imagen_router)
app.include_router(historial_router)
app.include_router(pdf_router)
app.include_router(procesar_imagen.router)