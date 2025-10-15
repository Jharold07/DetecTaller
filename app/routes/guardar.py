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
    emociones_json: str = Form(...),
    tiempo_procesamiento: float = Form(...),
):
    try:
        usuario_id = request.cookies.get("usuario_id")
        if not usuario_id:
            return {"error": "No se encontró el usuario"}
        
        try:
            emociones = json.loads(emociones_json)
        except Exception:
            return {"error": "Formato de emociones inválido"}

        inicios = [float(e["inicio"]) for e in emociones if "inicio" in e]
        fines   = [float(e["fin"])    for e in emociones if "fin" in e]
        if not inicios or not fines:
            return {"error": "Las emociones no contienen 'inicio' y 'fin'"}       


        form_data = await request.form()
        inicio_det = form_data.get("inicio_det")
        fin_det = form_data.get("fin_det")

        now = datetime.now()
        fecha = now.strftime("%Y-%m-%d")
        hora = now.strftime("%H:%M:%S")

        if video_nombre.startswith("http"):
            video_nombre = video_nombre.split("/")[-1]

        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )
        cursor = conn.cursor()            

        for emocion in emociones:
            cursor.execute("""
                INSERT INTO resultados_video 
                (nombre, edad, video, emocion, inicio, fin, usuario_id, fecha, hora, inicio_det, fin_det, tiempo_procesamiento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                nombre,
                edad,
                video_nombre,
                emocion["emocion"],
                emocion["inicio"],
                emocion["fin"],
                usuario_id,
                fecha,
                hora,
                inicio_det,
                fin_det,
                tiempo_procesamiento
            ))

        conn.commit()
        conn.close()
        cursor.close()
        
        return RedirectResponse(url="/historial", status_code=303)

    except Exception as e:
        return {"error": str(e)}
    