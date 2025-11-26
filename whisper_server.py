"""
Serveur Whisper distant avec CUDA + MFA pour analyse phonétique
À déployer sur mars.gregorymariani.com

Installation requise:
pip install torch transformers accelerate fastapi uvicorn python-multipart
pip install montreal-forced-aligner
# Puis: mfa model download acoustic russian_mfa
#      mfa model download dictionary russian_mfa
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import tempfile
import os
import logging
import subprocess
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Whisper Remote API")

# CORS pour permettre les requêtes depuis VoiceChat
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration globale
device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
model_id = "openai/whisper-large-v3-turbo"

logger.info(f"Loading Whisper model on {device}...")

# Chargement du modèle
model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id,
    torch_dtype=torch_dtype,
    low_cpu_mem_usage=True,
    use_safetensors=True
)
model.to(device)

processor = AutoProcessor.from_pretrained(model_id)

# Pipeline de transcription
pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    torch_dtype=torch_dtype,
    device=device,
    chunk_length_s=30,  # Pour les audios longs
    batch_size=1
)

logger.info("Whisper model loaded successfully!")

# Configuration MFA
MFA_MODELS = {
    "ru": {
        "acoustic": "russian_mfa",
        "dictionary": "russian_mfa"
    },
    "fr": {
        "acoustic": "french_mfa",
        "dictionary": "french_mfa"
    }
}

def check_mfa_installed():
    """Vérifie si MFA est installé"""
    try:
        result = subprocess.run(["mfa", "version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

MFA_AVAILABLE = check_mfa_installed()
if MFA_AVAILABLE:
    logger.info("✅ MFA disponible")
else:
    logger.warning("⚠️ MFA non installé - analyse phonétique désactivée")


@app.get("/")
async def root():
    return {
        "status": "online",
        "model": model_id,
        "device": device,
        "torch_dtype": str(torch_dtype)
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "gpu_available": torch.cuda.is_available(),
        "device": device
    }


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form(None)
):
    """
    Transcription audio avec Whisper large-v3-turbo.
    
    Args:
        audio: Fichier audio (mp3, wav, webm, etc.)
        language: Code langue (fr, ru, en, etc.) - optionnel
    
    Returns:
        {"text": "transcription", "language": "detected_lang"}
    """
    try:
        # Sauvegarder temporairement le fichier
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio.filename)[1]) as tmp_file:
            content = await audio.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        logger.info(f"Transcribing audio: {audio.filename} (language: {language or 'auto'})")
        
        # Configuration de génération
        generate_kwargs = {}
        if language:
            generate_kwargs["language"] = language
        
        # Transcription
        result = pipe(tmp_path, generate_kwargs=generate_kwargs)
        
        # Nettoyage
        os.unlink(tmp_path)
        
        response = {
            "text": result["text"].strip(),
            "language": language or "auto"
        }
        
        logger.info(f"Transcription success: {response['text'][:50]}...")
        return response
        
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe_batch")
async def transcribe_batch(
    audios: list[UploadFile] = File(...),
    language: str = Form(None)
):
    """
    Transcription en batch de plusieurs fichiers audio.
    """
    results = []
    
    for audio in audios:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio.filename)[1]) as tmp_file:
                content = await audio.read()
                tmp_file.write(content)
                tmp_path = tmp_file.name
            
            generate_kwargs = {}
            if language:
                generate_kwargs["language"] = language
            
            result = pipe(tmp_path, generate_kwargs=generate_kwargs)
            os.unlink(tmp_path)
            
            results.append({
                "filename": audio.filename,
                "text": result["text"].strip(),
                "language": language or "auto"
            })
            
        except Exception as e:
            logger.error(f"Error transcribing {audio.filename}: {str(e)}")
            results.append({
                "filename": audio.filename,
                "error": str(e)
            })
    
    return {"results": results}


@app.post("/analyze_phonemes")
async def analyze_phonemes(
    audio: UploadFile = File(...),
    text: str = Form(...),
    language: str = Form("ru")
):
    """
    Analyse phonétique avec Montreal Forced Aligner.
    
    Args:
        audio: Fichier audio
        text: Transcription attendue
        language: Code langue (ru, fr)
    
    Returns:
        {
            "phonemes": [{"phone": "p", "start": 0.0, "end": 0.1}, ...],
            "words": [{"word": "привет", "start": 0.0, "end": 0.5}, ...],
            "score": 85  # Score de prononciation estimé
        }
    """
    if not MFA_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="MFA non installé - analyse phonétique indisponible"
        )
    
    if language not in MFA_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Langue non supportée: {language}"
        )
    
    try:
        # Créer dossier temporaire pour MFA
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Sauvegarder audio
            audio_ext = os.path.splitext(audio.filename)[1]
            audio_path = tmpdir_path / f"audio{audio_ext}"
            content = await audio.read()
            with open(audio_path, "wb") as f:
                f.write(content)
            
            # Créer fichier texte avec transcription
            text_path = tmpdir_path / "audio.txt"
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(text.strip())
            
            # Dossier de sortie
            output_dir = tmpdir_path / "output"
            output_dir.mkdir()
            
            # Configuration MFA
            acoustic_model = MFA_MODELS[language]["acoustic"]
            dictionary_model = MFA_MODELS[language]["dictionary"]
            
            # Commande MFA align
            cmd = [
                "mfa", "align",
                str(tmpdir_path),  # Dossier input
                str(dictionary_model),
                str(acoustic_model),
                str(output_dir),  # Dossier output
                "--clean",
                "--single_speaker"
            ]
            
            logger.info(f"🔍 Lancement MFA: {' '.join(cmd)}")
            
            # Exécuter MFA
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"MFA error: {result.stderr}")
                raise HTTPException(
                    status_code=500,
                    detail=f"MFA alignment failed: {result.stderr[:200]}"
                )
            
            # Lire résultats TextGrid
            textgrid_path = output_dir / "audio.TextGrid"
            if not textgrid_path.exists():
                raise HTTPException(
                    status_code=500,
                    detail="TextGrid output not found"
                )
            
            # Parser TextGrid (format simple)
            phonemes, words = parse_textgrid(textgrid_path)
            
            # Calculer score (basé sur nombre de phonèmes alignés)
            score = min(100, len(phonemes) * 10)  # Heuristique simple
            
            return {
                "phonemes": phonemes,
                "words": words,
                "score": score,
                "language": language
            }
            
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="MFA timeout")
    except Exception as e:
        logger.error(f"Phoneme analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def parse_textgrid(textgrid_path: Path) -> tuple[list, list]:
    """
    Parse basique d'un fichier TextGrid.
    Retourne (phonemes, words).
    """
    phonemes = []
    words = []
    
    try:
        with open(textgrid_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Parsing simple (à améliorer selon format exact)
        # Format TextGrid: intervals avec xmin, xmax, text
        
        lines = content.split("\n")
        current_tier = None
        in_interval = False
        interval_data = {}
        
        for line in lines:
            line = line.strip()
            
            if "name = " in line:
                current_tier = line.split('"')[1] if '"' in line else None
            
            if "intervals [" in line:
                in_interval = True
                interval_data = {}
            
            if in_interval:
                if "xmin = " in line:
                    interval_data["start"] = float(line.split("=")[1].strip())
                elif "xmax = " in line:
                    interval_data["end"] = float(line.split("=")[1].strip())
                elif "text = " in line:
                    text = line.split('"')[1] if '"' in line else ""
                    interval_data["text"] = text
                    
                    if text and text != "":
                        if current_tier == "phones":
                            phonemes.append({
                                "phone": text,
                                "start": interval_data.get("start", 0),
                                "end": interval_data.get("end", 0)
                            })
                        elif current_tier == "words":
                            words.append({
                                "word": text,
                                "start": interval_data.get("start", 0),
                                "end": interval_data.get("end", 0)
                            })
                    
                    in_interval = False
        
        return phonemes, words
        
    except Exception as e:
        logger.error(f"TextGrid parsing error: {e}")
        return [], []


if __name__ == "__main__":
    import uvicorn
    
    # Lancer sur port 8001 pour ne pas conflictuer avec Ollama (11434) ou autres services
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
