import os, time, io, datetime
import numpy as np
import mysql.connector
import boto3
from fastapi import APIRouter, Request, File, UploadFile, Form
from fastapi.responses import HTMLResponse
from PIL import Image
from dotenv import load_dotenv

# --- ML / rostro ---
import cv2
import tensorflow as tf

load_dotenv()
router = APIRouter()

# ====== S3 ======
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)
BUCKET_NAME = os.getenv("BUCKET_NAME")  # p.ej. emociones-taller

# ====== MySQL ======
def get_conn():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE")
    )

# ====== Modelo y etiquetas (igual que en video) ======
# Carga 1 sola vez
MODELO = tf.keras.models.load_model(os.path.join("app", "models", "modelo_final.h5"))
EMOCIONES = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']

# ====== Validador de rostro: Haarcascade ======
FACE_CASCADE = cv2.CascadeClassifier(
    os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
)

def hay_rostro(im_bgr: np.ndarray) -> bool:
    gray = cv2.cvtColor(im_bgr, cv2.COLOR_BGR2GRAY)
    caras = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
    return len(caras) > 0

# ====== Util ======
def presigned(key: str, seconds: int = 3600) -> str:
    return s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET_NAME, 'Key': key},
        ExpiresIn=seconds
    )

def safe_filename(nombre: str, ext: str) -> str:
    base = "".join(ch if ch.isalnum() else "_" for ch in nombre).strip("_")
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{base}_{ts}{ext}"

# ====== ENDPOINT: predecir & guardar IMAGEN ======
@router.post("/predecir-imagen", response_class=HTMLResponse)
async def predecir_imagen(
    request: Request,
    imagen: UploadFile = File(...),
    nombre: str = Form(...),
    edad: int = Form(...)
):
    email = request.cookies.get("email")
    usuario_id = request.cookies.get("usuario_id")
    if not usuario_id:
        # Mantén el flujo de tu app (redirigir a /login si prefieres)
        return request.app.templates.TemplateResponse("login.html", {"request": request, "error": "No logueado"})

    try:
        inicio_det = datetime.now()

        raw = await imagen.read()
        file_arr = np.frombuffer(raw, np.uint8)
        im_bgr = cv2.imdecode(file_arr, cv2.IMREAD_COLOR)

        if im_bgr is None:
            return request.app.templates.TemplateResponse("index.html", {
                "request": request, "email": email,
                "error": "La imagen no es válida o está corrupta."
            })

        if not hay_rostro(im_bgr):
            return request.app.templates.TemplateResponse("index.html", {
                "request": request, "email": email,
                "error": "No se detectó rostro en la imagen. Intenta con otra."
            })

        im_rgb = cv2.cvtColor(im_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(im_rgb).convert("RGB").resize((224, 224))
        arr = np.asarray(pil).astype("float32") / 255.0
        arr = np.expand_dims(arr, axis=0)

        pred = MODELO.predict(arr, verbose=0)
        idx = int(np.argmax(pred[0]))
        emocion = EMOCIONES[idx]
        confianza = float(pred[0][idx] * 100.0)

        ext = os.path.splitext(imagen.filename or ".jpg")[1] or ".jpg"
        key = f"fotos/{safe_filename(nombre, ext)}"
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=raw, ContentType=imagen.content_type or "image/jpeg")

        fin_det = datetime.now()
        tiempo = round((fin_det - inicio_det).total_seconds(), 2)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO resultados_imagen
              (usuario_id, nombre, edad, imagen_path, emocion, confianza, tiempo_procesamiento, fecha, hora, inicio_det, fin_det)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURDATE(), CURTIME(), %s, %s)
        """, (int(usuario_id), nombre, int(edad), key, emocion, confianza, tiempo, inicio_det, fin_det))
        conn.commit()
        cur.close(); conn.close()

        url_imagen = presigned(key)
        return request.app.templates.TemplateResponse("index.html", {
            "request": request,
            "email": email,
            "emocion": emocion,
            "confianza": f"{confianza:.2f}%",
            "imagen_guardada": url_imagen,   
            "nombre": nombre,
            "edad": edad,
            "tiempo": tiempo,
        })

    except Exception as e:
        return request.app.templates.TemplateResponse("index.html", {
            "request": request, "email": email,
            "error": f"Error al procesar la imagen: {str(e)}"
        })