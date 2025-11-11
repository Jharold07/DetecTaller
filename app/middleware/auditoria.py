# app/middleware/auditoria.py
import time
import os
import mysql.connector
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

def _get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        autocommit=True,
    )

def _safe_user_id(request: Request):
    # Tus cookies actuales: 'usuario_id' y 'email'
    uid = request.cookies.get("usuario_id")
    try:
        return int(uid) if uid is not None else None
    except:
        return None

class AuditoriaMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        inicio = time.time()

        # Datos de la petición
        metodo   = request.method
        endpoint = request.url.path
        ip       = request.client.host if request.client else None
        ua       = request.headers.get("user-agent", "")[:255]
        uid      = _safe_user_id(request)

        # Ejecuta la vista
        response = None
        error_text = None
        try:
            response = await call_next(request)
            codigo = response.status_code
        except Exception as e:
            # Si la ruta rompe, igual registramos en bitácora
            codigo = 500
            error_text = str(e)[:1000]  # corta por seguridad
            raise
        finally:
            dur_ms = int((time.time() - inicio) * 1000)

            # Inserta en bitácora SIN bloquear la respuesta
            try:
                conn = _get_db()
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO bitacora_usuarios
                      (usuario_id, accion, endpoint, metodo, ip, agente_usuario, detalles, codigo_estado, dur_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        uid,
                        # Regla simple de "acción" a partir del endpoint/método
                        self._infer_accion(metodo, endpoint),
                        endpoint,
                        metodo,
                        ip,
                        ua,
                        error_text,     # si falló, queda el texto de error aquí
                        codigo,
                        dur_ms,
                    ),
                )
                cur.close()
                conn.close()
            except Exception:
                # Nunca reventar la app por un fallo de log
                pass

        return response

    def _infer_accion(self, metodo: str, endpoint: str) -> str:
        ep = endpoint.lower()
        if ep.startswith("/login"):
            return "LOGIN"
        if ep.startswith("/logout"):
            return "LOGOUT"
        if "procesar" in ep and metodo == "POST":
            return "PROCESAR"
        if "historial" in ep and metodo == "GET":
            return "VER_HISTORIAL"
        if "eliminar" in ep and metodo in ("DELETE", "POST"):
            return "ELIMINAR_REGISTRO"
        if "admin" in ep and "usuarios" in ep:
            return "ADMIN_USUARIOS"
        return f"{metodo}_{endpoint}"