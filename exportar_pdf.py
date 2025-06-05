from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, RedirectResponse
import sqlite3
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

router = APIRouter()
DB_PATH = "data/emociones.db"

@router.get("/exportar_pdf")
async def exportar_pdf(request: Request, nombre: str = "", emocion: str = "", fecha: str = ""):
    usuario_id = request.cookies.get("usuario_id")
    if not usuario_id:
        return RedirectResponse("/login")

    # Construir consulta dinámica
    query = '''
        SELECT nombre, edad, fecha, hora, emocion, tiempo_procesamiento
        FROM registros
        WHERE usuario_id = ?
    '''
    params = [usuario_id]

    if nombre:
        query += " AND nombre LIKE ?"
        params.append(f"%{nombre}%")
    if emocion:
        query += " AND lower(emocion) = ?"
        params.append(emocion.lower())
    if fecha:
        query += " AND fecha = ?"
        params.append(fecha)

    query += " ORDER BY fecha DESC, hora DESC"

    # Ejecutar la consulta
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, params)
    registros = cursor.fetchall()
    conn.close()

    # Crear PDF
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, "Historial de Emociones Detectadas")

    # Mostrar filtros aplicados
    filtro_y = height - 75
    filtros_aplicados = []
    if nombre:
        filtros_aplicados.append(f"Nombre = {nombre}")
    if emocion:
        filtros_aplicados.append(f"Emoción = {emocion}")
    if fecha:
        filtros_aplicados.append(f"Fecha = {fecha}")

    if filtros_aplicados:
        c.setFont("Helvetica", 10)
        c.drawString(50, filtro_y, f"Filtros aplicados: {', '.join(filtros_aplicados)}")
        filtro_y -= 15
    else:
        filtro_y -= 5

    # Escribir datos
    c.setFont("Helvetica", 10)
    y = filtro_y - 20
    for idx, r in enumerate(registros, 1):
        texto = f"{idx}. {r[0]} | Edad: {r[1]} | Fecha: {r[2]} {r[3]} | Emoción: {r[4]} | Tiempo: {r[5]}s"
        c.drawString(50, y, texto)
        y -= 18
        if y < 60:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 50

    c.save()
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=historial_emociones.pdf"
    })
