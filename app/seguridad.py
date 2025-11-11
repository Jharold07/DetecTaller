# app/seguridad.py
import os
import mysql.connector
from fastapi import Request, HTTPException, status
from typing import List, Optional

def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        autocommit=True,
    )

def obtener_usuario_actual(request: Request):
    usuario_id = request.cookies.get("usuario_id")
    if not usuario_id:
        return None

    try:
        usuario_id = int(usuario_id)
    except ValueError:
        return None

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT u.id, u.nombre, u.email, u.rol_id, u.estado, r.name AS rol
        FROM usuarios u
        LEFT JOIN roles r ON r.id = u.rol_id
        WHERE u.id = %s
    """, (usuario_id,))
    usuario = cur.fetchone()
    cur.close()
    conn.close()

    if not usuario:
        return None
    return usuario

def requerir_roles(usuario, roles_permitidos: list[str]):
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado"
        )
    if usuario["estado"] != "ACTIVO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    if usuario["rol"] not in roles_permitidos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
