import sqlite3

DB_PATH = "data/emociones.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    edad INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    emocion TEXT NOT NULL,
    imagen_path TEXT NOT NULL,
    usuario_id INTEGER NOT NULL,
    tiempo_procesamiento REAL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
)
""")

conn.commit()
conn.close()

print("Base de datos creada correctamente.")