import os
import httpx
import json
import asyncio
import edge_tts
import re

# Configuration
OLLAMA_URL = "http://192.168.1.28:11434"
MODEL_NAME = "llama3:8b"
WHISPER_API_URL = "http://mars.gregorymariani.com:8002"
WHISPER_V2_API_URL = "http://mars.gregorymariani.com:8002"

# Voix TTS par langue
VOICES = {
    "fr": "fr-FR-VivienneMultilingualNeural",
    "ru": "ru-RU-SvetlanaNeural"
}

class STTService:
    def __init__(self):
        self.api_url = WHISPER_API_URL
        self.v2_api_url = WHISPER_V2_API_URL
        print(f"Using remote Whisper API: {self.api_url}")
        print(f"Using remote Whisper V2 API: {self.v2_api_url}")

    async def transcribe(self, audio_path: str, language: str = None) -> str:
        """Transcribe audio using remote Whisper large-v3-turbo API"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Prepare the file for upload
                with open(audio_path, 'rb') as audio_file:
                    files = {'audio': (os.path.basename(audio_path), audio_file, 'audio/webm')}
                    data = {'language': language} if language else {}
                    
                    # Send request to remote API
                    response = await client.post(
                        f"{self.api_url}/transcribe",
                        files=files,
                        data=data
                    )
                    response.raise_for_status()
                    result = response.json()
                    return result['text'].strip()
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            raise
    
    async def analyze_phonemes(self, audio_path: str, expected_text: str, language: str) -> dict:
        """
        Analyse phonétique via MFA sur serveur distant.
        Retourne score et détails phonèmes.
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(audio_path, 'rb') as audio_file:
                    files = {'audio': (os.path.basename(audio_path), audio_file, 'audio/webm')}
                    data = {
                        'text': expected_text,
                        'language': language
                    }
                    
                    response = await client.post(
                        f"{self.api_url}/analyze_phonemes",
                        files=files,
                        data=data
                    )
                    
                    if response.status_code == 503:
                        # MFA non disponible
                        return {"available": False, "score": None}
                    
                    response.raise_for_status()
                    result = response.json()
                    result["available"] = True
                    return result
                    
        except Exception as e:
            print(f"⚠️ Phoneme analysis error: {e}")
            return {"available": False, "score": None, "error": str(e)}

    async def analyze_pronunciation_v2(self, audio_path: str, expected_text: str, language: str) -> dict:
        """
        Analyse avancée (V2) via WhisperX + Wav2Vec2 + Silero.
        Retourne score, phonèmes, et prosodie.
        """
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                with open(audio_path, 'rb') as audio_file:
                    files = {'audio': (os.path.basename(audio_path), audio_file, 'audio/webm')}
                    data = {
                        'text': expected_text,
                        'language': language
                    }
                    
                    response = await client.post(
                        f"{self.v2_api_url}/analyze_pronunciation",
                        files=files,
                        data=data
                    )
                    
                    response.raise_for_status()
                    result = response.json()
                    result["available"] = True
                    return result
                    
        except Exception as e:
            print(f"⚠️ V2 Analysis error: {e}")
            return {"available": False, "score": None, "error": str(e)}

class LLMService:
    def __init__(self, base_url=OLLAMA_URL, model=MODEL_NAME):
        self.base_url = base_url
        self.model = model

    async def chat(self, messages: list) -> str:
        """Appel API Ollama avec timing"""
        import time
        start_time = time.time()
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": False},
                    timeout=30.0
                )
                response.raise_for_status()
                elapsed = time.time() - start_time
                print(f"⏱️ LLM génération: {elapsed:.2f}s")
                return response.json()["message"]["content"]
            except Exception as e:
                print(f"❌ Erreur Ollama: {e}")
                return ""

    async def generate_lesson(self, user_text: str, native_lang: str, learning_lang: str) -> dict:
        """
        Génère une réponse pédagogique bilingue FR/RU uniquement.
        """
        
        # Détecter si l'utilisateur parle français ou russe
        is_russian = any('\u0400' <= c <= '\u04FF' for c in user_text)
        user_lang = "ru" if is_russian else "fr"
        
        # L'autre langue est la langue d'apprentissage
        teaching_lang = "ru" if user_lang == "fr" else "fr"
        
        system_prompt = f"""Tu es un professeur de langue pour l'apprentissage bidirectionnel français-russe.

RÈGLES CRITIQUES:
1. Si l'utilisateur parle FRANÇAIS → Réponds en FRANÇAIS + donne phrase RUSSE à pratiquer
2. Si l'utilisateur parle RUSSE → Réponds en RUSSE + donne phrase FRANÇAISE à pratiquer
3. Progression pédagogique: salutation → prénom → âge → ville → profession → loisirs
4. Phrases SIMPLES niveau A1-A2 (3-7 mots maximum)
5. Toujours donner la phrase COMPLÈTE à répéter, jamais juste "répète"

FORMAT JSON STRICT:
{{"segments": [{{"lang": "{user_lang}", "text": "encouragement/instruction"}}, {{"lang": "{teaching_lang}", "text": "phrase complète à pratiquer"}}]}}

EXEMPLES FRANÇAIS → RUSSE:

User: "Bonjour, je veux apprendre le russe"
{{"segments": [{{"lang": "fr", "text": "Parfait ! Dis bonjour en russe"}}, {{"lang": "ru", "text": "Привет"}}]}}

User: "Priviet"
{{"segments": [{{"lang": "fr", "text": "Excellent ! Maintenant présente-toi"}}, {{"lang": "ru", "text": "Меня зовут..."}}]}}

User: "Menya zovut Greg"
{{"segments": [{{"lang": "fr", "text": "Très bien Greg ! Demande comment ça va"}}, {{"lang": "ru", "text": "Как дела?"}}]}}

EXEMPLES RUSSE → FRANÇAIS:

User: "Привет, я хочу учить французский"
{{"segments": [{{"lang": "ru", "text": "Отлично! Скажи привет по-французски"}}, {{"lang": "fr", "text": "Bonjour"}}]}}

User: "Bonjour"
{{"segments": [{{"lang": "ru", "text": "Прекрасно! Теперь представься"}}, {{"lang": "fr", "text": "Je m'appelle..."}}]}}

IMPORTANT:
- JAMAIS de mélange de langues dans un même segment
- Toujours donner la phrase ENTIÈRE en langue cible (pas "répète X")
- Adapter les phrases russes au CONTEXTE (pas de traduction littérale)
- Si l'utilisateur répète mal → corriger gentiment et redemander
- Si l'utilisateur est perdu → revenir aux bases (Привет / Bonjour)

Réponds UNIQUEMENT en JSON valide."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]
        
        response = await self.chat(messages)
        return self._parse_response(response, user_lang, teaching_lang)
    
    def _parse_response(self, content: str, native_lang: str, learning_lang: str) -> dict:
        """Parse et valide la réponse JSON du LLM"""
        try:
            # Nettoyer markdown
            content = content.replace("```json", "").replace("```", "").strip()
            
            # Extraire JSON (premier objet uniquement)
            start = content.find('{')
            if start == -1:
                print(f"❌ Pas de JSON trouvé: {content[:200]}")
                return self._fallback_response("Erreur de format", native_lang)
            
            # Trouver la fin du premier objet JSON valide
            brace_count = 0
            end = start
            for i in range(start, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            
            json_str = content[start:end]
            
            # Debug: afficher le JSON extrait
            print(f"📋 JSON extrait: {json_str[:200]}")
            
            result = json.loads(json_str)
            
            # Valider structure
            if "segments" not in result or not isinstance(result["segments"], list):
                print(f"❌ Structure invalide: {result}")
                return self._fallback_response("Erreur de structure", native_lang)
            
            # Valider langues des segments
            result["segments"] = self._validate_segments(result["segments"])
            return result
                
        except json.JSONDecodeError as e:
            print(f"❌ Parse JSON: {e}")
            print(f"   Contenu: {content[:300]}")
            return self._fallback_response("Erreur de décodage", native_lang)
        except Exception as e:
            print(f"❌ Erreur inattendue: {e}")
            return self._fallback_response("Erreur système", native_lang)
    
    def _fallback_response(self, text: str, lang: str) -> dict:
        """Réponse de secours si parsing échoue"""
        error_messages = {
            "fr": "Une erreur s'est produite, pouvez-vous répéter",
            "ru": "Произошла ошибка, повторите пожалуйста"
        }
        return {
            "segments": [{"lang": lang, "text": error_messages.get(lang, error_messages["fr"])}]
        }
    
    def _validate_segments(self, segments: list) -> list:
        """Valide et corrige les langues des segments selon leur contenu"""
        validated = []
        
        for seg in segments:
            text = seg.get("text", "").strip()
            if not text:
                continue
            
            # Détection automatique
            detected_lang = self._detect_language(text)
            print(f"🔍 Segment détecté: lang={detected_lang}, text={text[:50]}...")
            
            validated.append({
                "lang": detected_lang,
                "text": text
            })
        
        return validated
    
    def _detect_language(self, text: str) -> str:
        """Détecte si texte est français ou russe basé sur les mots-clés puis le ratio de caractères"""
        text_lower = text.lower()
        
        # 1. Vérifier d'abord les mots français communs (priorité haute)
        french_words = ['le', 'la', 'les', 'un', 'une', 'de', 'du', 'je', 'tu', 'il', 
                       'est', 'comment', 'dit', 'on', 'en', 'à', 'au', 'et', 'mais',
                       'super', 'commence', 'par', 'dire', 'dis', 'bien', 'sûr',
                       'bonjour', 'salut', 'merci', 'oui', 'non', 'pour', 'avec']
        
        # Si on trouve plusieurs mots français → français
        french_word_count = sum(1 for word in french_words if f" {word} " in f" {text_lower} ")
        if french_word_count >= 2:  # Au moins 2 mots français
            return "fr"
        
        # 2. Patterns français typiques
        if any(p in text_lower for p in ["dit-on", "qu'", "c'est", "n'", "d'", "l'", "j'", "s'"]):
            return "fr"
        
        # 3. Compter les caractères cyrilliques vs latins (seulement si pas de mots français clairs)
        cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        latin_count = sum(1 for c in text if c.isalpha() and not ('\u0400' <= c <= '\u04FF'))
        
        # Si majorité cyrillique ET pas de mots français → russe
        if cyrillic_count > 0 and cyrillic_count > latin_count and french_word_count == 0:
            return "ru"
        
        # Par défaut français (alphabet latin)
        return "fr"
        return "fr"
    
    def evaluate_pronunciation(self, user_text: str, expected_text: str) -> dict:
        """
        Évalue basiquement la prononciation en comparant la transcription.
        Retourne score et feedback.
        """
        user_lower = user_text.lower().strip()
        expected_lower = expected_text.lower().strip()
        
        # Exact match = parfait
        if user_lower == expected_lower:
            return {"score": 100, "feedback": "Parfait"}
        
        # Calculer similarité simple (mots en commun)
        user_words = set(user_lower.split())
        expected_words = set(expected_lower.split())
        
        if not expected_words:
            return {"score": 0, "feedback": "Erreur"}
        
        common = user_words & expected_words
        similarity = len(common) / len(expected_words) * 100
        
        if similarity >= 80:
            return {"score": int(similarity), "feedback": "Très bien"}
        elif similarity >= 50:
            return {"score": int(similarity), "feedback": "Bien, attention à la prononciation"}
        else:
            return {"score": int(similarity), "feedback": "Essaie encore"}

class TTSService:
    @staticmethod
    def _clean_text(text: str) -> str:
        """Nettoie le texte pour TTS: enlève markdown et artefacts"""
        # Markdown
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'#+\s*', '', text)
        
        # Listes
        text = re.sub(r'^\s*[\-\*•]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        
        # Parenthèses et métadonnées
        text = re.sub(r'\([^)]*\)', '', text)
        text = re.sub(r'\b(Langue|Lang|Segment)\s*\d*\s*:\s*', '', text, flags=re.IGNORECASE)
        
        # Espaces multiples et retours ligne
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n+', ' ', text)
        
        return text.strip()
    
    async def generate_audio(self, text: str, lang: str, output_path: str):
        """Génère un fichier audio MP3"""
        clean_text = self._clean_text(text)
        voice = VOICES.get(lang, VOICES["fr"])
        
        communicate = edge_tts.Communicate(clean_text, voice)
        await communicate.save(output_path)
    
    async def generate_segments(self, segments: list, session_id: str) -> list:
        """Génère les fichiers audio pour tous les segments"""
        results = []
        
        for idx, seg in enumerate(segments):
            lang = seg.get("lang", "fr")
            text = seg.get("text", "").strip()
            
            if not text:
                continue
            
            filename = f"{session_id}_seg{idx}_{lang}.mp3"
            filepath = f"audio_cache/{filename}"
            
            await self.generate_audio(text, lang, filepath)
            
            results.append({
                "lang": lang,
                "text": text,
                "audio_url": f"/audio/{filename}"
            })
        
        return results

