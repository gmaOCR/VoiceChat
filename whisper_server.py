"""
Serveur Whisper distant avec CUDA
À déployer sur mars.gregorymariani.com

Installation requise:
pip install torch transformers accelerate fastapi uvicorn python-multipart
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import tempfile
import os
import logging

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


if __name__ == "__main__":
    import uvicorn
    
    # Lancer sur port 8001 pour ne pas conflictuer avec Ollama (11434) ou autres services
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
