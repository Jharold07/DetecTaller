from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import sqlite3
import boto3
import os
import matplotlib.pyplot as plt
import io
import base64
from dotenv import load_dotenv


load_dotenv()

router = APIRouter()

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)
BUCKET_NAME = os.getenv("BUCKET_NAME")

@router.get("/historial", response_class=HTMLResponse)
async def ver_historial(request: Request):
    usuario_id = request.cookies.get("usuario_id")
    if not usuario_id:
        return {"error": "No logueado"}

    # === Obtener filtros ===
    nombre_filtro = request.query_params.get("nombre", "").strip()
    emocion_filtro = request.query_params.get("emocion", "").strip()
    fecha_filtro = request.query_params.get("fecha", "").strip()

    conn = sqlite3.connect("data/emociones.db")
    cursor = conn.cursor()

    query = """
        SELECT video, fecha, hora, nombre, edad, emocion, inicio, fin
        FROM resultados_video
        WHERE usuario_id = ?
    """
    params = [usuario_id]

    if nombre_filtro:
        query += " AND nombre LIKE ?"
        params.append(f"%{nombre_filtro}%")

    if emocion_filtro:
        query += " AND emocion = ?"
        params.append(emocion_filtro)

    if fecha_filtro:
        query += " AND fecha = ?"
        params.append(fecha_filtro)

    query += " ORDER BY fecha DESC, hora DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    # Agrupar resultados por video, fecha, hora
    historial = []
    video_dict = {}

    for row in rows:
        key = (row[0], row[1], row[2])  # video, fecha, hora
        if key not in video_dict:
            video_dict[key] = {
                "video": s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': BUCKET_NAME, 'Key': row[0]},
                    ExpiresIn=3600  # URL válida por 1 hora
                ),
                "fecha": row[1],
                "hora": row[2],
                "nombre": row[3],
                "edad": row[4],
                "emociones": []
            }
        video_dict[key]["emociones"].append({
            "emocion": row[5],
            "inicio": row[6],
            "fin": row[7]
        })

    historial = list(video_dict.values())

    # Generar gráfico para cada video
    for v in historial:
        v["grafico"] = generar_grafico_tiempo(v["emociones"])

    return request.app.templates.TemplateResponse("historial.html", {
        "request": request,
        "historial": historial
    })

def generar_grafico_tiempo(emociones):
    fig, ax = plt.subplots(figsize=(8, 2))
    
    # Colores fijos por emoción
    colores_emociones = {
        "happy": "#32CD32",     # Verde lima
        "sad": "#1E90FF",       # Azul
        "angry": "#FF4500",     # Rojo anaranjado
        "neutral": "#808080",   # Gris
        "fear": "#8A2BE2",      # Púrpura
        "disgust": "#556B2F",   # Verde oliva oscuro
        "surprise": "#FFD700"   # Dorado
    }

    # Usamos un solo nivel vertical para todos
    y_pos = 0
    for emocion in emociones:
        color = colores_emociones.get(emocion["emocion"], "#AAAAAA")
        width = emocion["fin"] - emocion["inicio"]
        ax.barh(y_pos, width, left=emocion["inicio"],
                height=0.6,
                color=color,
                edgecolor='black',
                label=emocion["emocion"],
                linewidth=0.8)

    # Limpiar el eje Y
    ax.set_yticks([])
    ax.set_xlabel("Segundos")
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    # Mostrar solo leyendas únicas
    handles, labels = ax.get_legend_handles_labels()
    seen = set()
    unique = [(h, l) for h, l in zip(handles, labels) if not (l in seen or seen.add(l))]
    ax.legend(*zip(*unique), loc='upper center', bbox_to_anchor=(0.5, 1.35),
              ncol=4, fontsize='small', frameon=False)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight', dpi=100)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close()
    return encoded