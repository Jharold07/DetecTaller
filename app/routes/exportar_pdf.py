from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import mysql.connector
import os
from dotenv import load_dotenv

router = APIRouter()
load_dotenv()

@router.get("/exportar_pdf")
async def exportar_pdf(request: Request, nombre: str = "", emocion: str = "", fecha: str = ""):
    usuario_id = request.cookies.get("usuario_id")
    if not usuario_id:
        return RedirectResponse("/login")

    query = '''
        SELECT nombre, edad, fecha, hora, video, emocion, inicio, fin
        FROM resultados_video
        WHERE usuario_id = %s
    '''
    params = [usuario_id]

    if nombre:
        query += " AND nombre LIKE %s"
        params.append(f"%{nombre}%")
    if emocion:
        query += " AND lower(emocion) = %s"
        params.append(emocion.lower())
    if fecha:
        query += " AND fecha = %s"
        params.append(fecha)

    query += " ORDER BY fecha DESC, hora DESC"

    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE")
    )
    cursor = conn.cursor()
    cursor.execute(query, params)
    registros = cursor.fetchall()
    cursor.close()
    conn.close()

    agrupado = {}
    for row in registros:
        key = (row[0], row[1], row[2], row[3])  # nombre, edad, fecha, hora
        if key not in agrupado:
            agrupado[key] = []
        agrupado[key].append({
            "emocion": row[5],
            "inicio": row[6],
            "fin": row[7]
        })

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, "Reporte de historial de Emociones ")

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

    c.setFont("Helvetica", 10)
    y = filtro_y - 20
    for idx, ((nombre, edad, fecha, hora), emociones) in enumerate(agrupado.items(), 1):
        encabezado = f"{idx}. {nombre} | Edad: {edad} | Fecha: {fecha} {hora}"
        c.drawString(50, y, encabezado)
        y -= 15

        for e in emociones:
            detalle = f"   - {e['emocion']} (Inicio: {e['inicio']}s - Fin: {e['fin']}s)"
            c.drawString(60, y, detalle)
            y -= 15

        y -= 10

        if y < 60:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 50

    c.save()
    buffer.seek(0)

    c.drawString(50, height - 50, "Generado por DetectaEmocion")

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=historial_emociones.pdf"
    })
