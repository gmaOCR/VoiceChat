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
        Returns a dict with 'correction', 'explanation', and 'response'.
        """
        
        # Determine languages
        # source_lang: Language user SPOKE (e.g., 'ru' if practicing Russian)
        # target_lang: Language user WANTS TO LEARN (e.g., 'ru')
        # native_lang: The OTHER language (e.g., 'fr')
        
        if target_lang == "ru":
            native_lang = "fr"
            learning_lang = "ru"
            native_lang_name = "Français"
            learning_lang_name = "Russe"
        else:
            native_lang = "ru"
            learning_lang = "fr"
            native_lang_name = "Russe"
            learning_lang_name = "Français"

        # Construct System Prompt
        system_prompt = (
            f"Tu es un tuteur de langue expert. L'utilisateur apprend le {learning_lang_name} et parle {native_lang_name}. "
            f"Il vient de dire une phrase en {learning_lang_name} (ou a essayé). "
            "Ton objectif est de l'aider à s'améliorer tout en maintenant une conversation naturelle.\n\n"
            "Analyse sa phrase et fournis une réponse au format JSON strict (sans markdown, sans texte avant/après) avec les champs suivants :\n"
            "1. \"correction\": La phrase corrigée en {learning_lang_name}. Si elle était déjà parfaite, recopie-la simplement.\n"
            "2. \"explanation\": Une brève explication des erreurs ou un conseil utile en {native_lang_name} (sa langue maternelle). Si c'était parfait, félicite-le brièvement en {native_lang_name}.\n"
            "3. \"response\": Une réponse naturelle et engageante pour continuer la conversation, rédigée en {learning_lang_name}.\n\n"
            "Format JSON attendu:\n"
            "{\n"
            "  \"correction\": \"...\",\n"
            "  \"explanation\": \"...\",\n"
            "  \"response\": \"...\"\n"
            "}"
        )
        
        user_msg = f"Voici ma phrase (en {learning_lang_name}): {user_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ]
        
        content = await self.chat(messages)
        
        try:
            # Clean content (remove markdown code blocks if present)
            content = content.replace("```json", "").replace("```", "").strip()
            
            # Try to find JSON in the response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = content[start:end]
                # Fix potential bad escapes (basic)
                # json_str = json_str.replace("\\'", "'") # Sometimes LLMs escape single quotes
                return json.loads(json_str)
            else:
                # Fallback if JSON parsing fails
                return {
                    "correction": user_text, 
                    "explanation": "Désolé, je n'ai pas pu analyser la réponse correctement (Format invalide).", 
                    "response": content
                }
        except Exception as e:
            print(f"JSON Parse Error: {e} | Content: {content}")
            return {
                "correction": user_text, 
                "explanation": "Erreur de traitement de la réponse IA.", 
                "response": content
            }

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

