from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
import json
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv

router = APIRouter()
load_dotenv()

@router.post("/guardar")
async def guardar(
    request: Request,
    nombre: str = Form(...),
    edad: int = Form(...),
    video_nombre: str = Form(...),
    emociones_json: str = Form(...)
):
    try:
        emociones = json.loads(emociones_json)
        usuario_id = request.cookies.get("usuario_id")
        if not usuario_id:
            return {"error": "No se encontró el usuario"}

        now = datetime.now()
        fecha = now.strftime("%Y-%m-%d")
        hora = now.strftime("%H:%M:%S")

        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )
        cursor = conn.cursor()

        if video_nombre.startswith("http"):
            video_nombre = video_nombre.split("/")[-1]

        for emocion in emociones:
            cursor.execute("""
                INSERT INTO resultados_video 
                (nombre, edad, video, emocion, inicio, fin, usuario_id, fecha, hora)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                nombre,
                edad,
                video_nombre,
                emocion["emocion"],
                emocion["inicio"],
                emocion["fin"],
                usuario_id,
                fecha,
                hora
            ))

        conn.commit()
        conn.close()
        cursor.close()
        
        return RedirectResponse(url="/historial", status_code=303)

    except Exception as e:
        return {"error": str(e)}
    