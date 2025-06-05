from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
from passlib.hash import bcrypt
from starlette.responses import Response

templates = Jinja2Templates(directory="templates")
router = APIRouter()

DB_PATH = "data/emociones.db"

@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    try:
        return templates.TemplateResponse("login.html", {"request": request})
    except Exception as e:
        return HTMLResponse(f"<h2>ERROR EN /login: {str(e)}</h2>", status_code=500)

@router.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, usuario: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, password FROM usuarios WHERE email = ?", (usuario,))
    user = cursor.fetchone()
    conn.close()

    if user and bcrypt.verify(password, user[1]):
        response = RedirectResponse("/", status_code=302)
        response.set_cookie("usuario_id", str(user[0]))
        response.set_cookie("email", usuario)
        return response
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciales inválidas."})

@router.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register", response_class=HTMLResponse)
async def register_post(request: Request, email: str = Form(...), password: str = Form(...)):
    if not email or not password:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Todos los campos son obligatorios."})

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return templates.TemplateResponse("register.html", {"request": request, "error": "El correo ya está registrado."})

    hash_pass = bcrypt.hash(password)
    cursor.execute("INSERT INTO usuarios (email, password) VALUES (?, ?)", (email, hash_pass))
    conn.commit()
    conn.close()
    response = RedirectResponse("/login?mensaje=Cuenta+creada+correctamente", status_code=302)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("usuario_id")
    response.delete_cookie("email")
    return response
