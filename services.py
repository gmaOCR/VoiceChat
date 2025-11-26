import os
import httpx
import json
import asyncio
import edge_tts
import re
import difflib

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

    async def evaluate_teacher_quality(self, history: list) -> dict:
        """
        Évalue la qualité de l'enseignement basé sur l'historique.
        Retourne un rapport JSON.
        """
        if not history:
            return {"score": 0, "feedback": "Pas d'historique"}
            
        prompt = """Tu es un expert en pédagogie des langues. Analyse cette conversation entre un étudiant et un professeur IA.
        
        CRITÈRES D'ÉVALUATION:
        1. Séparation des langues (0-10): Est-ce que les langues sont bien séparées ?
        2. Pédagogie (0-10): Est-ce que la progression est logique ? Les traductions sont-elles données ?
        3. Correction (0-10): Est-ce que le prof corrige les erreurs de l'étudiant ?
        
        HISTORIQUE:
        """
        
        for msg in history:
            prompt += f"\n{msg['role']}: {msg['content']}"
            
        prompt += """
        
        Réponds UNIQUEMENT en JSON:
        {
            "scores": {"separation": X, "pedagogy": Y, "correction": Z},
            "global_score": N (moyenne),
            "strengths": ["..."],
            "weaknesses": ["..."],
            "verdict": "..."
        }
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.chat(messages)
        
        try:
            # Nettoyer et parser
            content = response.replace("```json", "").replace("```", "").strip()
            start = content.find('{')
            end = content.rfind('}') + 1
            return json.loads(content[start:end])
        except Exception as e:
            print(f"❌ Erreur évaluation qualité: {e}")
            return {"error": str(e)}

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calcule la similarité entre deux textes (0.0 à 1.0)"""
        return difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    async def generate_lesson(self, user_text: str, native_lang: str, learning_lang: str, history: list = None, expected_text: str = None) -> dict:
        """
        Génère une réponse pédagogique bilingue FR/RU avec séparation stricte des langues.
        
        Args:
            user_text: Texte de l'utilisateur
            native_lang: Langue maternelle (non utilisé, détection auto)
            learning_lang: Langue à apprendre (non utilisé, détection auto)
            history: Historique de conversation [{"role": "user/assistant", "content": "..."}]
            expected_text: Texte attendu pour l'exercice (validation stricte)
        """
        
        # Détecter si l'utilisateur parle français ou russe
        is_russian = any('\u0400' <= c <= '\u04FF' for c in user_text)
        user_lang = "ru" if is_russian else "fr"
        
        # L'autre langue est la langue d'apprentissage
        teaching_lang = "ru" if user_lang == "fr" else "fr"
        
        # Noms de langues pour le prompt
        lang_names = {
            "fr": {"name": "français", "script": "latin"},
            "ru": {"name": "russe", "script": "cyrillique"}
        }
        
        user_lang_name = lang_names[user_lang]["name"]
        teaching_lang_name = lang_names[teaching_lang]["name"]
        teaching_script = lang_names[teaching_lang]["script"]
        
        # Validation stricte de l'exercice
        validation_prompt = ""
        if expected_text:
            similarity = self.calculate_similarity(user_text, expected_text)
            print(f"🔍 Validation stricte: '{user_text}' vs '{expected_text}' (Sim: {similarity:.2f})")
            
            if similarity < 0.5:
                validation_prompt = f"""
                ⚠️ ALERTE VALIDATION:
                L'utilisateur devait dire: "{expected_text}"
                Mais il a dit: "{user_text}"
                
                CE N'EST PAS L'EXERCICE DEMANDÉ.
                1. NE LE FÉLICITE PAS pour sa prononciation.
                2. Dis-lui gentiment qu'il n'a pas répété la phrase demandée.
                3. S'il pose une question, réponds-y.
                4. Redemande-lui de faire l'exercice "{expected_text}".
                """
            else:
                validation_prompt = f"""
                ✅ VALIDATION OK:
                L'utilisateur essaie bien de dire "{expected_text}".
                Tu peux évaluer sa prononciation et passer à la suite.
                """
        
        system_prompt = f"""Tu es un professeur de {teaching_lang_name} pour des étudiants {user_lang_name}.

{validation_prompt}

🚨 RÈGLE ABSOLUE - SÉPARATION DES LANGUES 🚨

INTERDICTIONS STRICTES:
❌ JAMAIS mélanger {user_lang_name} et {teaching_lang_name} dans un même segment
❌ JAMAIS utiliser des caractères {teaching_script} dans le segment {user_lang_name}
❌ JAMAIS utiliser des mots {teaching_lang_name} dans le segment {user_lang_name}

FORMAT JSON OBLIGATOIRE:
{{
  "segments": [
    {{"lang": "{user_lang}", "text": "feedback/instruction avec TRADUCTION"}},
    {{"lang": "{teaching_lang}", "text": "phrase complète à pratiquer"}}
  ]
}}

RÈGLES DE TRADUCTION:
- TOUJOURS donner l'équivalent dans les deux langues
- Format: "Dis X en {teaching_lang_name}" puis donner X en {teaching_lang_name}
- Exemple FR→RU: "Maintenant ton âge. Dis 'J'ai 25 ans'" → "Мне 25 лет"
- Exemple RU→FR: "Теперь твой возраст. Скажи 'Мне 25 лет'" → "J'ai 25 ans"

UTILISATION DE L'HISTORIQUE:
- Consulter l'historique pour voir ce qui a déjà été enseigné
- NE PAS répéter les mêmes exercices
- Progresser logiquement: salutation → nom → âge → ville → profession
- Si l'étudiant a déjà dit son nom, passer à l'âge
- Si l'étudiant demande "encore", proposer le niveau suivant

EXEMPLES CORRECTS ✅:

Étudiant francophone apprenant le russe:

User: "Bonjour, je veux apprendre"
{{
  "segments": [
    {{"lang": "fr", "text": "Parfait ! Dis bonjour en russe"}},
    {{"lang": "ru", "text": "Привет"}}
  ]
}}

User: "Priviet"
{{
  "segments": [
    {{"lang": "fr", "text": "Excellent ! Maintenant présente-toi. Dis 'Je m'appelle...'"}},
    {{"lang": "ru", "text": "Меня зовут..."}}
  ]
}}

User: "Menya zovut Greg"
{{
  "segments": [
    {{"lang": "fr", "text": "Très bien Greg ! Maintenant ton âge. Dis 'J'ai ... ans'"}},
    {{"lang": "ru", "text": "Мне ... лет"}}
  ]
}}

Étudiant russophone apprenant le français:

User: "Привет, я хочу учить французский"
{{
  "segments": [
    {{"lang": "ru", "text": "Отлично! Скажи привет по-français"}},
    {{"lang": "fr", "text": "Bonjour"}}
  ]
}}

User: "Bonjour"
{{
  "segments": [
    {{"lang": "ru", "text": "Прекрасно! Теперь представься. Скажи 'Меня зовут...'"}},
    {{"lang": "fr", "text": "Je m'appelle..."}}
  ]
}}

User: "Je m'appelle Ivan"
{{
  "segments": [
    {{"lang": "ru", "text": "Отлично Иван! Теперь возраст. Скажи 'Мне ... лет'"}},
    {{"lang": "fr", "text": "J'ai ... ans"}}
  ]
}}

EXEMPLES INCORRECTS ❌:
❌ {{"lang": "fr", "text": "Dis ton âge"}} → Manque la traduction "J'ai ... ans"
❌ {{"lang": "ru", "text": "Мой prénom"}} → Mélange cyrillique + latin
❌ Répéter "Привет" si déjà enseigné → Utiliser l'historique pour progresser

PROGRESSION PÉDAGOGIQUE (niveau A1):
1. Salutation → Привет / Bonjour
2. Prénom → Меня зовут... / Je m'appelle...
3. Âge → Мне ... лет / J'ai ... ans
4. Ville → Я живу в... / J'habite à...
5. Profession → Я работаю... / Je travaille...

FEEDBACK CONSTRUCTIF:
- Si correct → féliciter + passer au suivant dans la progression
- Si erreur mineure → corriger gentiment + redemander
- Si erreur majeure → revenir à un exemple simple
- Si perdu → retour aux bases (salutation)
- Si demande "encore" → consulter historique et proposer le niveau suivant

IMPORTANT:
- Phrases COURTES (3-7 mots maximum)
- Vocabulaire SIMPLE niveau débutant
- TOUJOURS donner la traduction dans le segment {user_lang_name}
- TOUJOURS donner la phrase COMPLÈTE à répéter
- Créer un environnement SANS JUGEMENT
- UTILISER L'HISTORIQUE pour éviter les répétitions

Réponds UNIQUEMENT en JSON valide."""

        # Construire les messages avec historique
        messages = [{"role": "system", "content": system_prompt}]
        
        # Ajouter l'historique si disponible (limité aux 10 derniers échanges)
        if history:
            messages.extend(history[-10:])
        
        # Ajouter le message actuel
        messages.append({"role": "user", "content": user_text})
        
        response = await self.chat(messages)
        return self._parse_response(response, user_lang, teaching_lang, history)
    
    def _parse_response(self, content: str, native_lang: str, learning_lang: str, history: list = None) -> dict:
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
            
            # NOUVEAU: Valider la qualité de la réponse (pureté + pédagogie)
            if not self._validate_response_quality(result["segments"], native_lang, learning_lang, history):
                print(f"⚠️ Réponse rejetée par les guardrails, régénération...")
                return self._fallback_response("Erreur de qualité réponse", native_lang)
            
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
    
    def _validate_response_quality(self, segments: list, native_lang: str, learning_lang: str, history: list = None) -> bool:
        """
        Valide la qualité de la réponse :
        1. Pureté des langues (pas de mélange abusif)
        2. Présence de traductions (pédagogie)
        3. Pas de répétition abusive (si historique fourni)
        """
        
        # 1. Validation Pureté des Langues
        for seg in segments:
            lang = seg.get("lang")
            text = seg.get("text", "")
            
            if lang == "fr":
                # Vérifier absence de cyrillique dans segment français
                # EXCEPTION: Autoriser si c'est une citation courte (entre guillemets ou < 30% du texte)
                cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
                total_len = len(text)
                
                if cyrillic_count > 0:
                    ratio = cyrillic_count / total_len if total_len > 0 else 0
                    # Si plus de 30% de cyrillique et pas de guillemets, c'est suspect
                    if ratio > 0.3 and not ("'" in text or '"' in text):
                        print(f"❌ Trop de cyrillique dans segment FR ({ratio:.1%}): {text}")
                        return False
                    
            elif lang == "ru":
                # Vérifier présence majoritaire de cyrillique dans segment russe
                cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
                alpha_count = sum(1 for c in text if c.isalpha())
                
                # Si le segment contient des lettres et moins de 50% sont cyrilliques → erreur
                if alpha_count > 0 and cyrillic_count / alpha_count < 0.5:
                    print(f"❌ Pas assez de cyrillique dans segment RU: {text}")
                    return False

        # 2. Validation Pédagogique (Traductions)
        # On s'attend à avoir au moins un segment dans chaque langue
        langs_present = {seg.get("lang") for seg in segments}
        if "fr" not in langs_present or "ru" not in langs_present:
            print(f"❌ Manque une langue dans la réponse: {langs_present}")
            return False
            
        # 3. Validation Anti-Répétition (si historique)
        if history and len(history) >= 2:
            # Find the last assistant message in the history
            last_assistant_msg_content = ""
            for i in reversed(range(len(history))):
                if history[i]["role"] == "assistant":
                    last_assistant_msg_content = history[i]["content"]
                    break

            current_response = " | ".join([f"{seg['lang']}: {seg['text']}" for seg in segments])
            
            # If the response is identical to the previous assistant response
            if last_assistant_msg_content and last_assistant_msg_content == current_response:
                print(f"❌ Répétition détectée: {current_response}")
                return False

        return True
    
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

