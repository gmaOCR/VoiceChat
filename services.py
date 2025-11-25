import os
import httpx
import json
import asyncio
from faster_whisper import WhisperModel
import edge_tts
import tempfile

# Configuration
OLLAMA_URL = "http://192.168.1.28:11434"
MODEL_NAME = "llama3.1:8b" # Updated to available model

class STTService:
    def __init__(self):
        # Run on CPU with INT8 to be lightweight and compatible
        # If GPU is available, user can change device="cuda"
        print("Loading Whisper model...")
        self.model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("Whisper model loaded.")

    def transcribe(self, audio_path: str, language: str = None) -> str:
        segments, info = self.model.transcribe(audio_path, language=language)
        text = "".join([segment.text for segment in segments])
        return text.strip()

class LLMService:
    def __init__(self, base_url=OLLAMA_URL, model=MODEL_NAME):
        self.base_url = base_url
        self.model = model

    async def chat(self, messages: list) -> str:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": False},
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json()["message"]["content"]
            except Exception as e:
                print(f"Error calling Ollama: {e}")
                return "Désolé, je ne peux pas répondre pour le moment."

    async def correct_and_respond(self, user_text: str, source_lang: str, target_lang: str) -> dict:
        """
        Analyzes the user text for errors and generates a response.
        Returns a dict with 'correction' and 'response'.
        """
        
        # Prompt engineering
        if source_lang == "fr":
            system_prompt = (
                "Tu es un assistant linguistique utile. "
                "L'utilisateur apprend le Russe. Il va te parler en Russe (ou essayer). "
                "1. Corrige son texte s'il y a des erreurs grammaticales ou de formulation. Si c'est parfait, dis 'Aucune correction nécessaire'. "
                "2. Réponds ensuite à sa phrase de manière naturelle en Russe pour continuer la conversation. "
                "Réponds au format JSON: {\"correction\": \"...\", \"response\": \"...\"}"
            )
            user_msg = f"Voici ma phrase en Russe: {user_text}"
        else: # source_lang == "ru" (User learns French)
            system_prompt = (
                "Tu es un assistant linguistique utile. "
                "L'utilisateur apprend le Français. Il va te parler en Français (ou essayer). "
                "1. Corrige son texte s'il y a des erreurs grammaticales ou de formulation. Si c'est parfait, dis 'Aucune correction nécessaire'. "
                "2. Réponds ensuite à sa phrase de manière naturelle en Français pour continuer la conversation. "
                "Réponds au format JSON: {\"correction\": \"...\", \"response\": \"...\"}"
            )
            user_msg = f"Voici ma phrase en Français: {user_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ]
        
        # We need to force JSON output if possible, or parse it. 
        # Llama3 is usually good at following format instructions.
        content = await self.chat(messages)
        
        try:
            # Try to find JSON in the response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = content[start:end]
                return json.loads(json_str)
            else:
                return {"correction": content, "response": ""}
        except:
            return {"correction": content, "response": ""}

class TTSService:
    async def generate_audio(self, text: str, language: str, output_file: str):
        # Select voice based on language
        voice = "fr-FR-VivienneMultilingualNeural" if language == "fr" else "ru-RU-SvetlanaNeural"
        # Edge TTS voices might vary, using generic ones usually works or we list them.
        # Fallback to a known working voice if needed.
        # For French: fr-FR-VivienneMultilingualNeural
        # For Russian: ru-RU-SvetlanaNeural
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)

