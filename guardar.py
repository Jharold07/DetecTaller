from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
import sqlite3
import json
from datetime import datetime

router = APIRouter()
DB_PATH = "data/emociones.db"

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

        conn = sqlite3.connect("data/emociones.db")
        cursor = conn.cursor()

        for emocion in emociones:
            cursor.execute("""
                INSERT INTO resultados_video 
                (nombre, edad, video, emocion, inicio, fin, usuario_id, fecha, hora)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        return RedirectResponse(url="/historial", status_code=303)

    except Exception as e:
        return {"error": str(e)}
    