import speech_recognition as sr

def escuchar_y_convertir():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Escuchando... (hablá y esperá unos segundos de silencio)")
        audio = r.listen(source, timeout=None, phrase_time_limit=15)

    try:
        texto = r.recognize_google(audio, language="es-AR")
        print("🗣️ Texto detectado:", texto)
        return texto
    except sr.UnknownValueError:
        return "No se pudo entender el audio."
    except sr.RequestError as e:
        return f"Error al acceder al servicio de reconocimiento: {e}"
