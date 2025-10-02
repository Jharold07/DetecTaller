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
    imagen_path: str = Form(...),          # p.ej. 'fotos/juan_20250929.jpg'
    emocion: str = Form(...),
    confianza: str = Form(...),            # viene como "20.89" (sin %). Aun así normalizamos.
    tiempo_procesamiento: str = Form(...), # "0.72"
):
    usuario_id = request.cookies.get("usuario_id")
    if not usuario_id:
        return RedirectResponse("/login", status_code=303)

    try:
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
          (usuario_id, nombre, edad, imagen_path, emocion, confianza, tiempo_procesamiento, fecha, hora)
        VALUES
          (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE(), CURRENT_TIME());
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
            ),
        )
        conn.commit()
        cur.close()
        conn.close()

        # Regresa al historial
        return RedirectResponse("/historial", status_code=303)

    except Exception as e:
        return HTMLResponse(f"Error guardando imagen: {e}", status_code=500)
