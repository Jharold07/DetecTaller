import sqlite3
from datetime import datetime

conn = sqlite3.connect("data/emociones.db")
cursor = conn.cursor()

# Crear tabla resultados_video si no existe
cursor.execute("""
CREATE TABLE IF NOT EXISTS resultados_video (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    edad INTEGER NOT NULL,
    video TEXT NOT NULL,
    emocion TEXT NOT NULL,
    inicio INTEGER NOT NULL,
    fin INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL
)
""")

print("✅ Tabla resultados_video lista.")
conn.commit()
conn.close()
