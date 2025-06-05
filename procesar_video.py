import cv2
import numpy as np

def procesar_video(ruta_video, modelo, emociones):
    cap = cv2.VideoCapture(ruta_video)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    resultados = []
    rostro_detectado = False
    emocion_anterior = None
    inicio_emocion = 0
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_id = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_id += 1

        # Procesar un frame por segundo
        if frame_id % int(fps) != 0:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

        if len(faces) == 0:
            continue  # No hay rostro, pasar al siguiente frame
        else:
            rostro_detectado = True

        try:
            # Redimensionar para el modelo
            img = cv2.resize(frame, (224, 224))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img_array = np.array(img) / 255.0
            img_array = img_array.reshape(1, 224, 224, 3)

            pred = modelo.predict(img_array)
            emocion_idx = np.argmax(pred)
            emocion_actual = emociones[emocion_idx]

            segundo_actual = int(frame_id // fps)

            if emocion_anterior is None:
                emocion_anterior = emocion_actual
                inicio_emocion = segundo_actual

            elif emocion_actual != emocion_anterior:
                resultados.append({
                    "emocion": emocion_anterior,
                    "inicio": inicio_emocion,
                    "fin": segundo_actual
                })
                emocion_anterior = emocion_actual
                inicio_emocion = segundo_actual

        except Exception as e:
            continue

    # Guardar la última emoción
    if emocion_anterior is not None:
        resultados.append({
            "emocion": emocion_anterior,
            "inicio": inicio_emocion,
            "fin": int(frame_id // fps)
        })

    cap.release()

    if not rostro_detectado:
        return None  # ⚠️ No se detectó ningún rostro en todo el video

    return resultados