from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
import mysql.connector
import os
from dotenv import load_dotenv
from app.seguridad import get_db

load_dotenv()
templates = Jinja2Templates(directory="app/templates")
router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, usuario: str = Form(...), password: str = Form(...)):
    try:
        # Conexión usando get_db() para mantener consistencia
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Buscar usuario por email
        cursor.execute("""
            SELECT u.id, u.nombre, u.email, u.password, u.estado, r.name AS rol
            FROM usuarios u
            LEFT JOIN roles r ON r.id = u.rol_id
            WHERE u.email = %s
        """, (usuario,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        # Validar existencia
        if not user:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Credenciales inválidas."}
            )

        # Truncar password largo (por compatibilidad bcrypt)
        if len(password) > 72:
            password = password[:72]

        # Validar contraseña
        if not pwd_context.verify(password, user["password"]):
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Credenciales inválidas."}
            )

        # Validar estado
        if user["estado"] != "ACTIVO":
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Usuario inactivo. Contacta al administrador."}
            )

        # 🚀 Login OK: setear cookies necesarias
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie("usuario_id", str(user["id"]), httponly=True)
        response.set_cookie("email", user["email"], httponly=True)
        response.set_cookie("nombre", user["nombre"] or "", httponly=True)
        response.set_cookie("rol", user["rol"] or "", httponly=True)

        return response

    except Exception as e:
        print(f"ERROR LOGIN: {e}")
        return HTMLResponse(f"<h2>ERROR EN LOGIN: {str(e)}</h2>", status_code=500)

@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("usuario_id")
    return response