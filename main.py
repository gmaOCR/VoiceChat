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
            
        # 1. Transcribe
        # Whisper language codes: 'fr', 'ru'
        transcription = stt_service.transcribe(temp_audio_path, language=source_lang)
        logger.info(f"Transcription: {transcription}")
        
        if not transcription:
            return JSONResponse({"error": "No speech detected"}, status_code=400)

        # 2. LLM Correction & Response
        # If user speaks French (source_lang='fr'), they are learning Russian (target_lang='ru')?
        # Wait, usually:
        # User: "Je veux apprendre le Russe" -> Source=FR, Target=RU.
        # But if they speak, they speak in the target language usually?
        # Let's clarify the logic:
        # Scenario A: User is French, learning Russian.
        #   - User speaks Russian (badly). Source=RU.
        #   - AI corrects in French? Or corrects in Russian?
        #   - AI responds in Russian.
        
        # Let's assume the UI sends:
        # spoken_lang: The language the user IS speaking.
        # response_lang: The language the AI should respond in.
        
        # For the prompt logic in services.py:
        # If source_lang (spoken) is 'ru' -> User is trying to speak Russian.
        # We correct them and respond in Russian.
        
        result = await llm_service.correct_and_respond(transcription, source_lang, target_lang)
        correction = result.get("correction", "")
        ai_response_text = result.get("response", "")
        
        logger.info(f"Correction: {correction}")
        logger.info(f"Response: {ai_response_text}")

        # 3. TTS
        audio_filename = f"{session_id}_response.mp3"
        audio_output_path = f"audio_cache/{audio_filename}"
        
        if ai_response_text:
            # AI responds in the target language (same as spoken usually, or the other one?)
            # Usually conversation happens in one language.
            # If I practice Russian, I speak Russian, AI responds in Russian.
            # So TTS language should be source_lang (which is the language of the conversation).
            # Wait, if I am French and I speak French to translate?
            # The prompt says: "L'utilisateur apprend le Russe. Il va te parler en Russe."
            # So source_lang is 'ru'. AI responds in 'ru'.
            
            tts_lang = source_lang 
            await tts_service.generate_audio(ai_response_text, tts_lang, audio_output_path)
        
        return {
            "user_text": transcription,
            "correction": correction,
            "ai_response": ai_response_text,
            "audio_url": f"/audio/{audio_filename}" if ai_response_text else None
        }

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
