from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()

def _to_decimal(x: str) -> float:
    """Normaliza '20.89' o '20.89%' a float."""
    s = str(x).strip()
    if s.endswith("%"):
        s = s[:-1]
    return float(s)

@router.post("/guardar-imagen")
async def guardar_imagen(
    request: Request,
    nombre: str = Form(...),
    edad: str = Form(...),
    imagen_path: str = Form(...),
    emocion: str = Form(...),
    confianza: str = Form(...),
    tiempo_procesamiento: str = Form(...)
):
    usuario_id = request.cookies.get("usuario_id")
    if not usuario_id:
        return RedirectResponse("/login", status_code=303)

    try:
        inicio_det = 0.0
        fin_det = _to_decimal(tiempo_procesamiento)

        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE"),
        )
        cur = conn.cursor()

        sql = """
        INSERT INTO resultados_imagen
          (usuario_id, nombre, edad, imagen_path, emocion, confianza, tiempo_procesamiento, fecha, hora, inicio_det, fin_det)
        VALUES
          (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE(), CURRENT_TIME(), %s, %s);
        """
        cur.execute(
            sql,
            (
                int(usuario_id),
                nombre,
                int(edad),
                imagen_path,
                emocion,
                _to_decimal(confianza),
                _to_decimal(tiempo_procesamiento),
                inicio_det,
                fin_det
            ),
        )
        conn.commit()
        cur.close()
        conn.close()

        return RedirectResponse("/historial", status_code=303)

    except Exception as e:
        return HTMLResponse(f"Error guardando imagen: {e}", status_code=500)
