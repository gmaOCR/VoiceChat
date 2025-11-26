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

# Contexte de session pour suivi exercices
session_context = {}  # {session_id: {"last_exercise": "phrase_attendue", "lang": "ru"}}

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.post("/chat")
async def chat_endpoint(
    audio: UploadFile = File(...),
    source_lang: str = Form(...),  # Langue maternelle: 'fr' ou 'ru'
    target_lang: str = Form(...)   # Langue à apprendre: 'ru' ou 'fr'
):
    """
    Endpoint principal pour l'apprentissage de langue.
    
    Logique:
    - Étudiant FR apprenant RU: source_lang='fr', target_lang='ru'
    - IA répond en FR (explications) + RU (exemples)
    """
    import time
    start_total = time.time()
    
    session_id = str(uuid.uuid4())
    temp_audio_path = f"temp_uploads/{session_id}_{audio.filename}"
    
    try:
        # Sauvegarde audio
        start_save = time.time()
        with open(temp_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)
        logger.info(f"💾 Sauvegarde: {time.time() - start_save:.2f}s")
        
        # 1. STT - Transcription
        start_stt = time.time()
        transcription = await stt_service.transcribe(temp_audio_path, language=target_lang)
        stt_time = time.time() - start_stt
        logger.info(f"🎤 STT ({stt_time:.2f}s): {transcription}")
        
        if not transcription:
            return JSONResponse({"error": "Aucune parole détectée"}, status_code=400)
        
        # 2. LLM - Génération leçon bilingue
        start_llm = time.time()
        result = await llm_service.generate_lesson(transcription, source_lang, target_lang)
        llm_time = time.time() - start_llm
        
        segments = result.get("segments", [])
        logger.info(f"🧠 LLM ({llm_time:.2f}s): {len(segments)} segments")
        
        if not segments:
            return JSONResponse({"error": "Erreur génération réponse"}, status_code=500)
        
        # Évaluer prononciation si contexte existe
        pronunciation_data = None
        
        if session_id in session_context:
            ctx = session_context[session_id]
            if ctx.get("last_exercise") and ctx.get("lang") == target_lang:
                # Analyse avancée avec WhisperX V2
                try:
                    v2_result = await stt_service.analyze_pronunciation_v2(
                        temp_audio_path,
                        ctx["last_exercise"],
                        target_lang
                    )
                    
                    if v2_result.get("available"):
                        pronunciation_data = {
                            "score": v2_result.get("pronunciation_score", 0),
                            "words": v2_result.get("words", []),
                            "prosody": v2_result.get("prosody", {}),
                            "transcription": v2_result.get("transcription", "")
                        }
                        logger.info(f"🎯 Prononciation V2: {pronunciation_data['score']}% - {len(pronunciation_data['words'])} mots")
                except Exception as e:
                    logger.warning(f"⚠️ V2 analysis failed: {e}")
                    # Fallback sur analyse basique
                    eval_result = llm_service.evaluate_pronunciation(transcription, ctx["last_exercise"])
                    pronunciation_data = {
                        "score": eval_result["score"],
                        "feedback": eval_result["feedback"]
                    }
                    logger.info(f"🎯 Prononciation (fallback): {pronunciation_data['score']}% - {eval_result['feedback']}")
        
        # Sauvegarder dernier exercice (phrase en langue cible)
        last_exercise = None
        for seg in segments:
            if seg.get("lang") == target_lang:
                last_exercise = seg.get("text")
                break
        
        if last_exercise:
            session_context[session_id] = {
                "last_exercise": last_exercise,
                "lang": target_lang
            }
        
        # 3. TTS - Synthèse audio
        start_tts = time.time()
        audio_segments = await tts_service.generate_segments(segments, session_id)
        tts_time = time.time() - start_tts
        logger.info(f"🔊 TTS ({tts_time:.2f}s): {len(audio_segments)} fichiers")
        
        total_time = time.time() - start_total
        logger.info(f"⏱️ TOTAL: {total_time:.2f}s | STT:{stt_time:.1f}s ({stt_time/total_time*100:.0f}%) LLM:{llm_time:.1f}s ({llm_time/total_time*100:.0f}%) TTS:{tts_time:.1f}s ({tts_time/total_time*100:.0f}%)")
        
        response_data = {
            "user_text": transcription,
            "segments": segments,
            "audio_segments": audio_segments
        }
        
        if pronunciation_data:
            response_data["pronunciation"] = pronunciation_data
        
        return response_data
    
    except Exception as e:
        logger.error(f"❌ Erreur: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
    
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
