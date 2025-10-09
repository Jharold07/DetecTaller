from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import mysql.connector
import boto3
import os
import matplotlib
import matplotlib.pyplot as plt
import io
import base64
from dotenv import load_dotenv


load_dotenv()
router = APIRouter()

matplotlib.use("Agg")

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

    email = request.cookies.get("email")
    nombre_filtro = request.query_params.get("nombre", "").strip()
    emocion_filtro = request.query_params.get("emocion", "").strip()
    fecha_filtro = request.query_params.get("fecha", "").strip()

    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE")
    )
    cursor = conn.cursor()

    query = """
        SELECT
            id, usuario_id, nombre, edad,
            archivo,          -- S3 key (video o imagen)
            emocion,
            confianza,        -- NULL en video
            tiempo_procesamiento, -- NULL en video
            inicio,           -- NULL en imagen
            fin,              -- NULL en imagen
            fecha,
            hora,
            tipo              -- 'video' | 'imagen'
        FROM vw_historial
        WHERE usuario_id = %s
    """
    params = [usuario_id]

    if nombre_filtro:
        query += " AND nombre LIKE %s"
        params.append(f"%{nombre_filtro}%")

    if emocion_filtro:
        query += " AND emocion %s"
        params.append(emocion_filtro)

    if fecha_filtro:
        query += " AND fecha = %s"
        params.append(fecha_filtro)

    query += " ORDER BY fecha DESC, hora DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    videos_map = {}
    imagenes = []

    for (
        _id, _uid, nombre, edad, archivo, emocion, confianza,
        tiempo_proc, inicio, fin, fecha, hora, tipo
    ) in rows:
        
        if tipo == 'video':
            s3_key = f"videos/{archivo}" if not archivo.startswith("videos/") else archivo
        else:
            s3_key = f"fotos/{archivo}" if not archivo.startswith("fotos/") else archivo
        
        # URL firma S3
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=3600
        )

        if tipo == 'video':
            key = (archivo, str(fecha), str(hora))
            if key not in videos_map:
                videos_map[key] = {
                    "tipo": "video",
                    "archivo": url,
                    "fecha": str(fecha),
                    "hora": str(hora),
                    "nombre": nombre,
                    "edad": edad,
                    "emociones": []          
                } 

            if inicio is not None and fin is not None:
                videos_map[key]["emociones"].append({
                    "emocion": emocion,
                    "inicio": inicio,
                    "fin": fin
                })
        else:  
            imagenes.append({
                "tipo": "imagen",
                "archivo": url,
                "fecha": str(fecha),
                "hora": str(hora),
                "nombre": nombre,
                "edad": edad,
                "emocion": emocion,
                "confianza": float(confianza) if confianza is not None else None,
                "tiempo_procesamiento": float(tiempo_proc) if tiempo_proc is not None else None
            })

    historial = list(videos_map.values()) + imagenes 

    # Generar gráfico
    for item in historial:
        if item["tipo"] == "video" and item["emociones"]:
            item["grafico"] = generar_grafico_tiempo(item["emociones"])

    return request.app.templates.TemplateResponse("historial.html", {
        "request": request,
        "historial": historial,
        "email": email
    })

def generar_grafico_tiempo(emociones):
    fig, ax = plt.subplots(figsize=(8, 2))
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

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", bbox_inches='tight', dpi=100)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close()
    return encoded