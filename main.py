from fastapi import FastAPI, Form, UploadFile, Request, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from auth import router as auth_router
from guardar import router as guardar_router
from historial import router as historial_router
from procesar_video import procesar_video
from exportar_pdf import router as pdf_router
import tensorflow as tf
import os
import json
import boto3
import time
from datetime import datetime
from s3_utils import s3, BUCKET_NAME 
import shutil
from dotenv import load_dotenv
from botocore.exceptions import NoCredentialsError


# === Cargar variables de entorno ===
load_dotenv()

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)
BUCKET_NAME = os.getenv("BUCKET_NAME")

# === Inicializar la app ===
app = FastAPI()

# Montar archivos estáticos y templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.templates = templates 

# Modelo y etiquetas
modelo = tf.keras.models.load_model("modelo_final.h5")
emociones = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']

# === Rutas ===
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


@app.post("/subir-video/", response_class=HTMLResponse)
async def subir_video(
    request: Request,
    video: UploadFile = Form(...),
    nombre: str = Form(...),
    edad: str = Form(...)
):
    # === 1. Subir a S3 ===
    try:
        s3.upload_fileobj(video.file, BUCKET_NAME, video.filename)
    except Exception as e:
        return HTMLResponse(content=f"❌ Error al subir video a S3: {e}", status_code=500)

    # === 2. Procesar video desde S3 ===
    # AWS no permite acceso directo al contenido de un objeto sin descargarlo,
    # así que descargamos temporalmente para procesar
    ruta_local = f"temp_{video.filename}"
    try:
        s3.download_file(BUCKET_NAME, video.filename, ruta_local)
        resultados = procesar_video(ruta_local, modelo, emociones)
        os.remove(ruta_local)
    except Exception as e:
        return HTMLResponse(content=f"❌ Error al procesar el video: {e}", status_code=500)

    # === 3. Renderizar resultados ===
    return templates.TemplateResponse("index.html", {
        "request": request,
        "emociones_detectadas": json.dumps(resultados),
        "nombre": nombre,
        "edad": edad,
        "video_nombre": video.filename
    })

@app.get("/protegido")
async def protegido(request: Request):
    if not request.cookies.get("usuario_id"):
        return RedirectResponse("/login")
    return HTMLResponse("Contenido privado")


app.include_router(auth_router)
app.include_router(guardar_router)
app.include_router(historial_router)
app.include_router(pdf_router)