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

#  Funciones para ayudar al usuario a traducir códigos de estado y acciones técnicas

def traducir_codigo_estado(codigo: int | None) -> str:
    if codigo is None:
        return "Sin código"
    if codigo == 200:
        return "200 - Operación exitosa"
    if codigo in (301, 302, 303, 307, 308):
        return f"{codigo} - Redirección (navegación interna)"
    if codigo == 400:
        return "400 - Solicitud incorrecta"
    if codigo == 401:
        return "401 - No autenticado"
    if codigo == 403:
        return "403 - Sin permisos"
    if codigo == 404:
        return "404 - Recurso no encontrado"
    if 500 <= codigo < 600:
        return f"{codigo} - Error interno del servidor"
    return str(codigo)

def traducir_accion_legible(row: dict) -> str:
    """
    Convierte endpoint/método/acción técnica en un mensaje entendible.
    Preferimos el campo 'accion' si viene seteado desde el middleware.
    """
    accion = (row.get("accion") or "").upper()
    endpoint = row.get("endpoint") or ""
    metodo = (row.get("metodo") or "").upper()

    if accion == "LOGIN":
        return "Inicio de sesión"
    if accion == "LOGOUT":
        return "Cierre de sesión"
    if accion == "SUBIR_VIDEO":
        return "Subió un video para análisis"
    if accion == "SUBIR_IMAGEN":
        return "Subió una imagen para análisis"
    if accion == "VER_HISTORIAL":
        return "Consultó el historial de resultados"
    if accion == "ADMIN_USUARIOS":
        return "Gestionó usuarios del sistema"

    if endpoint.startswith("/login") and metodo == "POST":
        return "Intento de inicio de sesión"
    if endpoint == "/" and metodo == "GET":
        return "Ingresó a la página principal"
    if "/subir" in endpoint and metodo == "POST":
        return "Subió un archivo para análisis"
    if "/historial" in endpoint:
        return "Visitó la página de historial"
    if "/admin/usuarios" in endpoint:
        return "Accedió al panel de administración de usuarios"

    return f"Acción en {endpoint} ({metodo})"


@router.get("/admin/usuarios")
def vista_usuarios(request: Request):
    """
    Panel de administración:
      - Gestión de usuarios
      - Reporte de resultados de todos los terapeutas
    Solo accesible para ADMIN.
    """
    usuario = obtener_usuario_actual(request)
    requerir_roles(usuario, ["ADMIN"])

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Usuarios
    cur.execute(
        """
        SELECT u.id, u.nombre, u.email, u.rol_id, u.estado, r.name AS rol
        FROM usuarios u
        LEFT JOIN roles r ON r.id = u.rol_id
        ORDER BY u.id ASC
        """
    )
    usuarios = cur.fetchall()

    # Roles disponibles
    cur.execute(
        "SELECT id, name FROM roles WHERE name IN ('TERAPEUTA', 'TERCERO') ORDER BY id"
    )
    roles_disponibles = cur.fetchall()

    # Reporte de los resultados de los tearupeutas
    cur.execute(
        """
        SELECT
            rv.nombre AS paciente,
            GROUP_CONCAT(DISTINCT rv.emocion ORDER BY rv.emocion SEPARATOR ', ') AS emociones_detectadas,
            MAX(rv.inicio_det)              AS inicio_deteccion,
            MAX(rv.fin_det)                 AS fin_deteccion,
            MAX(rv.tiempo_procesamiento)    AS tiempo_procesamiento,
            MAX(rv.precision_global)        AS precision_global,
            MAX(rv.fecha)                   AS fecha,
            MAX(rv.hora)                    AS hora
        FROM resultados_video rv
        JOIN usuarios u ON u.id = rv.usuario_id
        JOIN roles r     ON r.id = u.rol_id
        WHERE r.name = 'TERAPEUTA'
        GROUP BY rv.nombre
        ORDER BY MAX(rv.fecha) ASC, MAX(rv.hora) ASC
        """
    )
    reportes = cur.fetchall()

    # Logs de auditoría (últimos 500 eventos)
    cur.execute(
        """
        SELECT 
            b.id,
            b.usuario_id,
            u.nombre AS usuario_nombre,
            u.email  AS usuario_email,
            r.name   AS usuario_rol,
            b.accion,
            b.endpoint,
            b.metodo,
            b.ip,
            b.codigo_estado,
            b.dur_ms,
            b.creado_en
        FROM bitacora_usuarios b
        LEFT JOIN usuarios u ON u.id = b.usuario_id
        LEFT JOIN roles r    ON r.id = u.rol_id
        ORDER BY b.creado_en DESC
        LIMIT 500
        """
    )
    logs_raw = cur.fetchall()

    cur.close()
    conn.close()

    for idx, row in enumerate(reportes, start=1):
        row["id_reporte"] = idx

    logs = []
    for row in logs_raw:
        logs.append({
            "id": row["id"],
            "fecha_hora": row["creado_en"],
            "usuario": row["usuario_nombre"] or row["usuario_email"] or "Desconocido",
            "rol": row["usuario_rol"] or "-",
            "ip": row["ip"] or "-",
            "accion_legible": traducir_accion_legible(row),
            "codigo_estado_legible": traducir_codigo_estado(row["codigo_estado"]),
            "dur_ms": row["dur_ms"],
        })

    return templates.TemplateResponse(
        "usuarios.html",
        {
            "request": request,
            "usuario_actual": usuario,
            "usuarios": usuarios,
            "roles_disponibles": roles_disponibles,
            "reportes": reportes,
            "logs": logs,  
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
        # Redirigimos con un query param simple
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
