from fastapi import APIRouter, Request, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.hash import bcrypt
import os
import mysql.connector

from app.seguridad import obtener_usuario_actual, requerir_roles

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        autocommit=True,
    )


def get_role_id(nombre_rol: str) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM roles WHERE name = %s", (nombre_rol,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se encontró el rol {nombre_rol}",
        )
    return row[0]


@router.get("/admin/usuarios")
def vista_usuarios(request: Request):
    """
    Listado y gestión básica de usuarios.
    Solo accesible para ADMIN.
    """
    usuario = obtener_usuario_actual(request)
    requerir_roles(usuario, ["ADMIN"])

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT u.id, u.nombre, u.email, u.rol_id, u.estado, r.name AS rol
        FROM usuarios u
        LEFT JOIN roles r ON r.id = u.rol_id
        ORDER BY u.id ASC
        """
    )
    usuarios = cur.fetchall()

    # Traemos roles permitidos para asignar (solo TERAPEUTA y TERCERO)
    cur.execute(
        "SELECT id, name FROM roles WHERE name IN ('TERAPEUTA', 'TERCERO') ORDER BY id"
    )
    roles_disponibles = cur.fetchall()

    cur.close()
    conn.close()

    return templates.TemplateResponse(
        "usuarios.html",
        {
            "request": request,
            "usuario_actual": usuario,
            "usuarios": usuarios,
            "roles_disponibles": roles_disponibles,
        },
    )


@router.post("/admin/usuarios/crear")
def crear_usuario(
    request: Request,
    nombre: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    rol: str = Form(...),
):
    """
    Crear usuarios nuevos como TERAPEUTA o TERCERO.
    Solo ADMIN. No se permite crear ADMIN desde la web.
    """
    usuario = obtener_usuario_actual(request)
    requerir_roles(usuario, ["ADMIN"])

    rol = rol.upper().strip()
    if rol not in ("TERAPEUTA", "TERCERO"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol no permitido. Solo TERAPEUTA o TERCERO.",
        )

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Verificar si ya existe email
    cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
    if cur.fetchone():
        cur.close()
        conn.close()
        # Redirigimos con un query param simple; luego se puede mostrar mensaje en la plantilla
        return RedirectResponse(
            url="/admin/usuarios?error=EMAIL_EXISTE",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    rol_id = get_role_id(rol)
    password_hash = bcrypt.hash(password)

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO usuarios (nombre, email, password, rol_id, estado)
        VALUES (%s, %s, %s, %s, 'ACTIVO')
        """,
        (nombre, email, password_hash, rol_id),
    )

    cur.close()
    conn.close()

    return RedirectResponse(
        url="/admin/usuarios?ok=CREADO",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/admin/usuarios/{usuario_id}/cambiar-estado")
def cambiar_estado_usuario(request: Request, usuario_id: int):
    """
    Activar / desactivar usuario.
    Reglas:
      - Solo ADMIN.
      - No puede desactivar su propia cuenta.
    """
    usuario = obtener_usuario_actual(request)
    requerir_roles(usuario, ["ADMIN"])

    if usuario["id"] == usuario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cambiar tu propio estado.",
        )

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT id, estado FROM usuarios WHERE id = %s", (usuario_id,))
    u = cur.fetchone()
    if not u:
        cur.close()
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    nuevo_estado = "INACTIVO" if u["estado"] == "ACTIVO" else "ACTIVO"

    cur = conn.cursor()
    cur.execute(
        "UPDATE usuarios SET estado = %s WHERE id = %s",
        (nuevo_estado, usuario_id),
    )

    cur.close()
    conn.close()

    return RedirectResponse(
        url="/admin/usuarios?ok=ESTADO",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/admin/usuarios/{usuario_id}/cambiar-rol")
def cambiar_rol_usuario(request: Request, usuario_id: int, rol: str = Form(...)):
    """
    Cambiar rol entre TERAPEUTA y TERCERO.
    No permite asignar ADMIN desde la web.
    No permite que un ADMIN se modifique a sí mismo aquí (para evitar dejar el sistema sin admins).
    """
    usuario = obtener_usuario_actual(request)
    requerir_roles(usuario, ["ADMIN"])

    if usuario["id"] == usuario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cambiar tu propio rol desde esta vista.",
        )

    rol = rol.upper().strip()
    if rol not in ("TERAPEUTA", "TERCERO"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol no permitido.",
        )

    rol_id = get_role_id(rol)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE usuarios SET rol_id = %s WHERE id = %s",
        (rol_id, usuario_id),
    )
    cur.close()
    conn.close()

    return RedirectResponse(
        url="/admin/usuarios?ok=ROL",
        status_code=status.HTTP_303_SEE_OTHER,
    )
