from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
import mysql.connector
import os
from dotenv import load_dotenv

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
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            port=os.getenv("MYSQL_PORT"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM usuarios WHERE email = %s", (usuario,))
        user = cursor.fetchone()
        conn.close()

        if user:
            if len(password) > 72:
                    password = password[:72]

            if pwd_context.verify(password, user[1]):
                    response = RedirectResponse(url="/", status_code=302)
                    response.set_cookie("usuario_id", str(user[0]))
                    return response

        return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciales inválidas."})

    except Exception as e:
        print(f"ERROR LOGIN: {e}")
        return HTMLResponse(f"<h2>ERROR EN LOGIN: {str(e)}</h2>", status_code=500)

@router.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register", response_class=HTMLResponse)
async def register_post(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        if not email or not password:
            return templates.TemplateResponse("register.html", {"request": request, "error": "Todos los campos son obligatorios."})

        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            port=os.getenv("MYSQL_PORT"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
        if cursor.fetchone():
            conn.close()
            return templates.TemplateResponse("register.html", {"request": request, "error": "El correo ya está registrado."})

        if len(password) > 72:
            password = password[:72]

        hash_pass = pwd_context.hash(password)

        cursor.execute("INSERT INTO usuarios (email, password) VALUES (%s, %s)", (email, hash_pass))
        conn.commit()
        conn.close()

        return RedirectResponse(url="/login?mensaje=Cuenta+creada+correctamente", status_code=302)

    except Exception as e:
        print(f"🔴 ERROR REGISTER: {e}")
        return HTMLResponse(f"<h2>ERROR EN REGISTRO: {str(e)}</h2>", status_code=500)


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("usuario_id")
    return response