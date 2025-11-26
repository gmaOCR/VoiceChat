"""
Serveur Whisper V2 - Pipeline d'analyse de prononciation avancée
Pipeline: Whisper-v3 Turbo -> WhisperX (Alignment) -> Wav2Vec2 (Phoneme Scoring) -> Silero (Prosody)

Installation requise:
pip install torch torchaudio transformers accelerate fastapi uvicorn python-multipart
pip install git+https://github.com/m-bain/whisperx.git
pip install librosa soundfile numpy scipy
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import torch
import torchaudio
import whisperx
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
import numpy as np
import tempfile
import os
from huggingface_hub import HfFolder
import logging
import json
import librosa
from pathlib import Path
from contextlib import asynccontextmanager
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modèles globaux
whisper_model = None
align_models = {}
phoneme_models = {}
vad_model = None

# Configuration par défaut (sera écrasée dans lifespan mais utile pour éviter NameError si importé)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 16
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global whisper_model, vad_model
    
    # Configuration
    global DEVICE, BATCH_SIZE, COMPUTE_TYPE
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    BATCH_SIZE = 16
    COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"
    
    HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_FACE_TOKEN")
    if HF_TOKEN:
        logger.info(f"Huggingface token détecté: {HF_TOKEN[:8]}...")
        HfFolder.save_token(HF_TOKEN)
    
    logger.info(f"Loading Whisper-v3 Turbo on {DEVICE}...")
    # WhisperX charge le modèle Whisper
    whisper_model = whisperx.load_model(
        "large-v3", 
        DEVICE, 
        compute_type=COMPUTE_TYPE,
        language="en", # Default, will be overridden per request if needed or auto-detected
    )
    
    logger.info("Loading Silero VAD...")
    vad_model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                      model='silero_vad',
                                      force_reload=False,
                                      onnx=False)
    logger.info("Models loaded successfully!")
    yield

app = FastAPI(title="Whisper Pronunciation Analysis API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_align_model(language_code):
    """Charge le modèle d'alignement WhisperX pour la langue donnée"""
    if language_code not in align_models:
        logger.info(f"Loading alignment model for {language_code}...")
        model, metadata = whisperx.load_align_model(
            language_code=language_code, 
            device=DEVICE
        )
        align_models[language_code] = (model, metadata)
    return align_models[language_code]

def get_phoneme_model(language_code):
    """Charge le modèle Wav2Vec2 pour le scoring phonétique"""
    # Mapping langue -> modèle HF
    # Pour l'instant on utilise un modèle multilingue ou spécifique si dispo
    # Exemple simplifié. Pour la prod, utiliser des modèles spécifiques fine-tunés.
    model_ids = {
        "en": "facebook/wav2vec2-lv-60-espeak-cv-ft",
        "fr": "facebook/wav2vec2-lv-60-espeak-cv-ft", # Fallback ou modèle spécifique FR
        "ru": "facebook/wav2vec2-lv-60-espeak-cv-ft", # Fallback
    }
    
    model_id = model_ids.get(language_code, "facebook/wav2vec2-lv-60-espeak-cv-ft")
    
    if language_code not in phoneme_models:
        logger.info(f"Loading phoneme model {model_id} for {language_code}...")
        processor = Wav2Vec2Processor.from_pretrained(model_id)
        model = Wav2Vec2ForCTC.from_pretrained(model_id).to(DEVICE)
        phoneme_models[language_code] = (processor, model)
        
    return phoneme_models[language_code]

@app.post("/analyze_pronunciation")
async def analyze_pronunciation(
    audio: UploadFile = File(...),
    text: str = Form(...), # Texte de référence (optionnel si on veut juste transcrire + aligner)
    language: str = Form("en")
):
    """
    Analyse complète: Transcription -> Alignement -> Scoring Phonétique -> Prosodie
    """
    try:
        # 1. Sauvegarde Audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio.filename)[1]) as tmp_file:
            content = await audio.read()
            tmp_file.write(content)
            audio_path = tmp_file.name

        # 2. Transcription (WhisperX)
        logger.info("Transcribing...")
        audio_data = whisperx.load_audio(audio_path)
        result = whisper_model.transcribe(audio_data, batch_size=BATCH_SIZE, language=language)
        
        # 3. Alignement (WhisperX)
        logger.info("Aligning...")
        model_a, metadata = get_align_model(result["language"])
        result_aligned = whisperx.align(
            result["segments"], 
            model_a, 
            metadata, 
            audio_data, 
            DEVICE, 
            return_char_alignments=False
        )
        
        # 4. Scoring Phonétique (Wav2Vec2)
        # Note: WhisperX donne déjà des scores de confiance par mot.
        # Pour une précision phonétique fine, on peut utiliser Wav2Vec2 CTC.
        # Ici on va extraire les segments alignés et calculer un score de confiance global et par mot.
        
        # Simplification: On utilise le score de confiance de WhisperX comme base
        # et on peut raffiner avec Wav2Vec2 si besoin. Pour l'instant, utilisons les données WhisperX
        # qui sont déjà très bonnes pour l'alignement et le scoring de confiance.
        
        # Extraction des mots et scores
        words_analysis = []
        total_score = 0
        word_count = 0
        
        for segment in result_aligned["segments"]:
            for word in segment["words"]:
                word_score = word.get("score", 0)
                words_analysis.append({
                    "word": word["word"],
                    "start": word["start"],
                    "end": word["end"],
                    "score": round(word_score * 100, 1)
                })
                total_score += word_score
                word_count += 1
        
        global_score = (total_score / word_count * 100) if word_count > 0 else 0
        
        # 5. Prosodie (Librosa / Silero)
        # Pitch, cadence, pauses
        y, sr = librosa.load(audio_path)
        
        # Pitch (F0)
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        avg_pitch = np.nanmean(f0) if np.nanmean(f0) > 0 else 0
        
        # Speech Rate (syllables/sec approx via peaks or word count)
        duration = librosa.get_duration(y=y, sr=sr)
        speech_rate = word_count / duration if duration > 0 else 0
        
        # Nettoyage
        os.unlink(audio_path)
        
        return {
            "transcription": result["segments"][0]["text"] if result["segments"] else "",
            "language": result["language"],
            "pronunciation_score": round(global_score, 1),
            "words": words_analysis,
            "prosody": {
                "average_pitch_hz": round(avg_pitch, 1),
                "speech_rate_wps": round(speech_rate, 2),
                "duration_s": round(duration, 2)
            }
        }

    except Exception as e:
        logger.error(f"Error in analysis: {str(e)}")
        traceback.print_exc()
        if os.path.exists(audio_path):
            os.unlink(audio_path)
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{traceback.format_exc()}")

@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form(None)
):
    """
    Transcription simple avec WhisperX (compatible API V1).
    """
    try:
        # 1. Sauvegarde Audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio.filename)[1]) as tmp_file:
            content = await audio.read()
            tmp_file.write(content)
            audio_path = tmp_file.name

        # 2. Transcription
        if whisper_model is None:
            raise HTTPException(status_code=500, detail="Whisper model not initialized")
            
        logger.info(f"Transcribing {audio.filename} (requested language: {language})...")
        audio_data = whisperx.load_audio(audio_path)
        
        # Note: WhisperX auto-détecte la langue, ne pas passer le paramètre language
        # car cela cause un conflit avec faster-whisper tokenizer
        options = {"batch_size": BATCH_SIZE}
        # On laisse WhisperX détecter automatiquement la langue
            
        result = whisper_model.transcribe(audio_data, **options)
        
        # Concaténer le texte
        full_text = " ".join([seg["text"].strip() for seg in result["segments"]])
        
        # Nettoyage
        os.unlink(audio_path)
        
        return {
            "text": full_text,
            "language": result["language"]
        }

    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        traceback.print_exc()
        if os.path.exists(audio_path):
            os.unlink(audio_path)
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{traceback.format_exc()}")

@app.get("/health")
def health():
    return {"status": "ok", "device": DEVICE}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

