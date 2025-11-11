# app/routes/backup.py

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import os, subprocess, tempfile, gzip, shutil

from app.seguridad import obtener_usuario_actual, requerir_roles
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")

# ===============================
# PANEL PRINCIPAL DEL ROL TERCERO
# ===============================
@router.get("/backup", response_class=HTMLResponse)
async def backup_page(request: Request):
    usuario = obtener_usuario_actual(request)
    requerir_roles(usuario, ["TERCERO"])

    ultimo = None  

    return templates.TemplateResponse(
        "backup.html",
        {
            "request": request,
            "usuario": usuario,
            "ultimo_backup": ultimo,
        },
    )


# ===============================
# GENERAR Y DESCARGAR BACKUP
# ===============================
@router.get("/backup/generar")
async def generar_backup(request: Request):
    usuario = obtener_usuario_actual(request)
    requerir_roles(usuario, ["TERCERO"])

    mysql_host = os.getenv("MYSQL_HOST")
    mysql_port = os.getenv("MYSQL_PORT", "3306")
    mysql_user = os.getenv("MYSQL_USER")
    mysql_password = os.getenv("MYSQL_PASSWORD")
    mysql_db = os.getenv("MYSQL_DATABASE")

    # Permite configurar ruta explícita si mysqldump no está en PATH (Windows)
    mysqldump_bin = os.getenv("MYSQLDUMP_PATH", "mysqldump")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{mysql_db}_{timestamp}.sql"
    backup_dir = os.path.join(os.getcwd(), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    filepath = os.path.join(backup_dir, filename)

    cmd = [
        mysqldump_bin,
        f"-h{mysql_host}",
        f"-P{mysql_port}",
        f"-u{mysql_user}",
        f"-p{mysql_password}",
        "--routines",
        "--events",
        "--triggers",
        mysql_db,
    ]

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            result = subprocess.run(
                cmd, stdout=f, stderr=subprocess.PIPE, text=True
            )

        if result.returncode != 0:
            # si falla, borra archivo vacío
            if os.path.exists(filepath):
                os.remove(filepath)
            raise HTTPException(
                status_code=500,
                detail=f"Error al generar backup: {result.stderr.strip()}",
            )

        # Aquí podrías registrar en bitácora que se generó un backup

        return FileResponse(
            filepath,
            filename=filename,
            media_type="application/sql",
        )

    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar backup: {str(e)}",
        )