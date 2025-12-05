from fastapi import FastAPI, UploadFile, File, Form, Request
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

# Historique de conversation par session
conversation_history = {}  # {session_id: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}

# Contexte de session pour suivi exercices
session_context = {}  # {session_id: {"last_exercise": "phrase_attendue", "lang": "ru"}}

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.post("/chat")
async def chat_endpoint(
    audio: UploadFile = File(...),
    source_lang: str = Form(...),  # Langue maternelle: 'fr' ou 'ru'
    target_lang: str = Form(...),   # Langue à apprendre: 'ru' ou 'fr'
    level: str = Form("A1")        # Niveau de compétence
):
    """
    Endpoint principal pour l'apprentissage de langue.
    """
    import time
    start_total = time.time()
    
    logger.info(f"📝 Request Params - Level: {level}, Source: {source_lang}, Target: {target_lang}")
    
    session_id = str(uuid.uuid4())
    temp_audio_path = f"temp_uploads/{session_id}_{audio.filename}"
    
    try:
        # Save audio code...
        start_save = time.time()
        with open(temp_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)
        file_size = os.path.getsize(temp_audio_path)
        logger.info(f"💾 Sauvegarde: {time.time() - start_save:.2f}s | Taille: {file_size} bytes")
        
        # 1. STT - Transcription
        start_stt = time.time()
        # Ensure we don't force language=None if we want auto-detect, 
        # but logic says None = auto-detect.
        transcription = await stt_service.transcribe(temp_audio_path, language=None)
        stt_time = time.time() - start_stt
        logger.info(f"🎤 STT ({stt_time:.2f}s): {transcription}")
        
        if not transcription:
            return JSONResponse({"error": "Aucune parole détectée"}, status_code=400)
            
        # 1.5 Retry Logic (Fix Translation Hallucinations)
        # If Whisper outputs English but user likely spoke Source/Target lang, force retry.
        detected = llm_service._detect_language(transcription)
        if detected == "en":
            logger.info(f"⚠️ English detected ('{transcription}'). Retrying with forced source language '{source_lang}'...")
            transcription_retry = await stt_service.transcribe(temp_audio_path, language=source_lang)
            
            # Check if retry yielded better result (not English)
            detected_retry = llm_service._detect_language(transcription_retry)
            if detected_retry != "en":
                logger.info(f"✅ Retry successful! New text: '{transcription_retry}'")
                transcription = transcription_retry
            else:
                logger.info(f"⚠️ Retry still English: '{transcription_retry}'. Trying forced target language '{target_lang}'...")
                # Last resort: Try target language
                transcription_final = await stt_service.transcribe(temp_audio_path, language=target_lang)
                if llm_service._detect_language(transcription_final) != "en":
                     logger.info(f"✅ Target retry successful! New text: '{transcription_final}'")
                     transcription = transcription_final
                else:
                     logger.info("❌ All retries failed. Keeping original English.")
        
        # 2. LLM - Génération leçon bilingue avec historique
        start_llm = time.time()
        
        # Récupérer l'historique de cette session
        session_history = conversation_history.get(session_id, [])
        
        # Récupérer le texte attendu (dernier exercice)
        expected_text = None
        if session_id in session_context:
            ctx = session_context[session_id]
            if ctx.get("lang") == target_lang:
                expected_text = ctx.get("last_exercise")
        
        # Générer la leçon avec contexte et validation
        result = await llm_service.generate_lesson(
            transcription, 
            source_lang, 
            target_lang,
            history=session_history,
            expected_text=expected_text,
            level=level
        )
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
        # On ne génère PAS l'audio pour la langue maternelle (source_lang / native_lang)
        # source_lang is passed as form data, verify variable name availability
        
        # In chat_endpoint signatures: source_lang is available.
        audio_segments = await tts_service.generate_segments(segments, session_id, skip_lang=source_lang)
        tts_time = time.time() - start_tts
        logger.info(f"🔊 TTS ({tts_time:.2f}s): {len(audio_segments)} fichiers")
        
        total_time = time.time() - start_total
        logger.info(f"⏱️ TOTAL: {total_time:.2f}s | STT:{stt_time:.1f}s ({stt_time/total_time*100:.0f}%) LLM:{llm_time:.1f}s ({llm_time/total_time*100:.0f}%) TTS:{tts_time:.1f}s ({tts_time/total_time*100:.0f}%)")
        
        response_data = {
            "user_text": transcription,
            "segments": segments,
            "audio_segments": audio_segments,
            "user_analysis": result.get("user_analysis")
        }
        
        if pronunciation_data:
            response_data["pronunciation"] = pronunciation_data
        
        # Mettre à jour l'historique de conversation
        if session_id not in conversation_history:
            conversation_history[session_id] = []
        
        # Ajouter l'échange actuel à l'historique
        conversation_history[session_id].append({"role": "user", "content": transcription})
        
        # Construire la réponse de l'assistant (texte des segments)
        assistant_response = " | ".join([f"{seg['lang']}: {seg['text']}" for seg in segments])
        conversation_history[session_id].append({"role": "assistant", "content": assistant_response})
        
        # Limiter l'historique à 20 messages (10 échanges)
        if len(conversation_history[session_id]) > 20:
            conversation_history[session_id] = conversation_history[session_id][-20:]
        
        return response_data
    
    except Exception as e:
        logger.error(f"❌ Erreur: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
    
    finally:
        # Nettoyage fichier temporaire
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

@app.post("/start")
async def start_endpoint(
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    level: str = Form("A1")
):
    """Démarre la session avec un message de bienvenue de l'IA."""
    session_id = str(uuid.uuid4())
    logger.info(f"🚀 Starting session {session_id} - Level: {level}")
    
    # Store context
    session_context[session_id] = {
        "lang": target_lang,
        "level": level,
        "last_exercise": None,
        "native_lang": source_lang
    }
    
    # Generate greeting
    retry_count = 0
    segments = []
    while retry_count < 2:
        try:
            result = await llm_service.generate_greeting(source_lang, target_lang, level)
            segments = result.get("segments", [])
            break
        except Exception as e:
            logger.error(f"Greeting generation failed: {e}")
            retry_count += 1
            if retry_count == 2:
                # Fallback hardcoded
                segments = [
                    {"lang": source_lang, "text": "Bienvenue ! Commençons."},
                    {"lang": target_lang, "text": "Привет! Давай начнем." if target_lang == "ru" else "Bonjour !"}
                ]

    # TTS
    try:
        # Skip source_lang audio
        audio_segments = await tts_service.generate_segments(segments, session_id, skip_lang=source_lang)
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        return JSONResponse({"error": "TTS Error"}, status_code=500)
        
    return {
        "session_id": session_id,
        "response": {
            "segments": segments,
            "user_analysis": {"is_correct": True, "explanation": "Session started."} 
        },
        "audio_segments": audio_segments
    }

@app.get("/evaluate_quality")
async def evaluate_quality(request: Request):
    """Évalue la qualité pédagogique de la session actuelle"""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in conversation_history:
        return JSONResponse({"error": "Pas d'historique pour cette session"}, status_code=404)
        
    history = conversation_history[session_id]
    report = await llm_service.evaluate_teacher_quality(history)
    return JSONResponse(report)

@app.get("/debug/history")
async def debug_history(request: Request):
    """Affiche l'historique de la session (debug)"""
    session_id = request.cookies.get("session_id")
    return JSONResponse(conversation_history.get(session_id, []))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
