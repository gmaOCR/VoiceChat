from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from services import STTService, LLMService, TTSService
import shutil
import os
import uuid
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Ensure directories exist
os.makedirs("static", exist_ok=True)
os.makedirs("audio_cache", exist_ok=True)
os.makedirs("temp_uploads", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/audio", StaticFiles(directory="audio_cache"), name="audio")

# Initialize Services
stt_service = STTService()
llm_service = LLMService()
tts_service = TTSService()

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.post("/chat")
async def chat_endpoint(
    audio: UploadFile = File(...),
    source_lang: str = Form(...), # 'fr' or 'ru' (Language the user speaks)
    target_lang: str = Form(...)  # 'ru' or 'fr' (Language the user wants to learn/hear)
):
    session_id = str(uuid.uuid4())
    temp_audio_path = f"temp_uploads/{session_id}_{audio.filename}"
    
    try:
        # Save uploaded audio
        with open(temp_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)
            
        # 1. Transcribe with remote Whisper API
        # Force transcription in the TARGET language (the one being learned/practiced)
        # This prevents misdetection when user speaks target language with accent
        # Example: User selects "Apprendre Français" -> target_lang='fr' -> transcribe in French
        transcription = await stt_service.transcribe(temp_audio_path, language=target_lang)
        logger.info(f"Transcription (lang={target_lang}): {transcription}")
        
        if not transcription:
            return JSONResponse({"error": "No speech detected"}, status_code=400)

        # 2. LLM Correction & Response
        # If user speaks French (source_lang='fr'), they are learning Russian (target_lang='ru')?
        # Wait, usually:
        # User: "Je veux apprendre le Russe" -> Source=FR, Target=RU.
        # Let's clarify the logic:
        # Scenario A: User is French, learning Russian.
        #   - User speaks Russian (badly). Source=RU.
        #   - AI corrects in French? Or corrects in Russian?
        #   - AI responds in Russian.
        # 2. LLM Correction & Response (avec détection de langue et segments)
        result = await llm_service.correct_and_respond(transcription, source_lang, target_lang)
        detected_lang = result.get("detected_input_lang", target_lang)
        correction = result.get("correction", "")
        segments = result.get("segments", [])
        
        logger.info(f"Detected input language: {detected_lang}")
        logger.info(f"Correction: {correction}")
        logger.info(f"Segments: {segments}")

        # 3. TTS - Génération audio segmentée (sans répétition de l'input utilisateur)
        audio_segments = []
        if segments:
            audio_segments = await tts_service.generate_segmented_audio(segments, session_id)
        
        return {
            "user_text": transcription,
            "detected_input_lang": detected_lang,
            "correction": correction,
            "segments": segments,
            "audio_segments": audio_segments
        }

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
