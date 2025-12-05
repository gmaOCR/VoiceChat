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
                    file_size = os.path.getsize(audio_path)
                    print(f"📤 Sending audio to Whisper: {file_size} bytes")
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

    async def generate_lesson(self, user_text: str, native_lang: str, learning_lang: str, history: list = None, expected_text: str = None, level: str = "A1") -> dict:
        """
        Génère une réponse pédagogique bilingue FR/RU avec séparation stricte des langues.
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
        
        
    async def generate_greeting(self, native_lang: str, learning_lang: str, level: str = "A1") -> dict:
        """Génère un message de bienvenue pour commencer la session."""
        user_lang_name = "Français" if native_lang == "fr" else "Russe"
        teaching_lang_name = "Russe" if learning_lang == "ru" else "Français"
        
        system_prompt = f"""Tu es un partenaire de conversation en {teaching_lang_name} (style Gliglish).
NIVEAU ÉTUDIANT: {level}.

TA MISSION:
Salue l'utilisateur chaleureusement et pose une première question simple pour lancer la discussion.
L'objectif est de mettre l'utilisateur en confiance dès le début.

RÈGLES:
1. Adapte le niveau ({level}).
2. Sois bref et amical.
3. Termine par une question.

FORMAT JSON:
{{
  "segments": [
    {{"lang": "{native_lang}", "text": "Salutation + Traduction de la question ({user_lang_name})"}},
    {{"lang": "{learning_lang}", "text": "Salutation + Question ({teaching_lang_name})"}}
  ]
}}
"""
        messages = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "user", "content": "Commence la session."})
        
        print(f"🎬 Generating greeting for level {level}...")
        response = await self.chat(messages)
        
        return self._parse_response(response, native_lang, learning_lang, [])

    async def generate_lesson(self, user_text: str, native_lang: str, learning_lang: str, history=None, expected_text=None, level="A1") -> dict:
        """
        Génère une réponse structurée (analyse + segments audio) via LLM.
        """
        user_lang_name = "Français" if native_lang == "fr" else "Russe"
        teaching_lang_name = "Russe" if learning_lang == "ru" else "Français"
        
        # 0. Check Input Language (Guardrail)
        detected_input_lang = self._detect_language(user_text)
        if detected_input_lang == "en":
            print(f"⛔ Input detected as English: {user_text}")
            return {
                "user_analysis": {
                    "is_correct": False,
                    "corrected_text": "",
                    "explanation": f"I detected English ('{user_text}'). Please speak {user_lang_name} or {teaching_lang_name}."
                },
                "segments": [
                    {"lang": native_lang, "text": f"J'ai entendu de l'anglais ({user_text}). Merci de parler {user_lang_name} ou {teaching_lang_name}."},
                    {"lang": learning_lang, "text": "Пожалуйста, говорите по-русски." if learning_lang == "ru" else "S'il vous plaît, parlez français."}
                ]
            }
        
        # Mapping level to description
        level_descriptions = {
            "A1": "Débutant: Phrases très simples, vocabulaire de base.",
            "A2": "Élémentaire: Phrases simples, vie quotidienne.",
            "B1": "Intermédiaire: Discours plus cohérent, expression d'opinions.",
            "B2": "Intermédiaire supérieur: Discours fluide et spontané.",
            "C1": "Avancé: Langue souple et efficace.",
            "C2": "Maîtrise: Précision et nuance."
        }
        level_desc = level_descriptions.get(level, level_descriptions["A1"])

        teaching_script = "cyrillique" if learning_lang == "ru" else "latin"

        context_prompt = ""
        # Si on attendait une phrase spécifique
        if expected_text:
            context_prompt = f"""
CONTEXTE EXERCICE PRÉCÉDENT:
L'utilisateur devait dire : "{expected_text}"
Analyse ce que l'utilisateur a dit ("{user_text}") :
1. Si c'est une tentative de répétition/réponse : Corrige la phonétique/grammaire.
2. Si c'est une question ou un commentaire en {user_lang_name} (ex: "Quels sont les exercices?", "Je ne comprends pas") : ALORS ignore la correction de la phrase précédente. Réponds à la question et propose un NOUVEL exercice.

NE T'ACHARNE PAS sur la phrase précédente si l'utilisateur veut passer à autre chose.
"""

        system_prompt = f"""Tu es un partenaire de conversation en {teaching_lang_name} (et professeur bienveillant) pour un étudiant {user_lang_name}.
NIVEAU: {level}.

PHILOSOPHIE (Style "Gliglish"):
- **Conversation avant tout**: On discute. Ne fais pas de "cours magistral".
- **Réaction immédiate**: Réagis à ce que dit l'utilisateur ("Ah bon ?", "C'est super !", "Je vois.").
- **Correction douce**: Si l'utilisateur fait une erreur, donne la bonne version dans ta réponse ou une section dédiée, mais ne bloque pas la discussion.
- **Questions**: Termine TOUJOURS par une question pour relancer l'utilisateur.

STRUCTURE DE RÉPONSE IDÉALE:
1. **Validaton/Réaction** (Ex: "C'est intéressant !", "D'accord.")
2. **Correction** (Si nécessaire, courte et précise).
3. **Relance** (Question ouverte liée au sujet).

RÈGLES PAR NIVEAU:
- A1/A2: Phrases courtes. Vocabulaire simple. Pose des questions simples (Oui/Non, Choix).
- B1/B2: Conversation fluide. Corrige les erreurs de temps ou de genre importantes. Questions ouvertes ("Pourquoi ?", "Comment ?").
- C1/C2: Débat naturel, expressions idiomatiques, argot. Comporte-toi comme un ami natif.

GÉRER L'IMPRÉVU:
- Si l'utilisateur dit n'importe quoi ("Je mange des chaises") -> Réagis avec humour ou demande clarification, mais continue.
- Si l'utilisateur insulte ou est hors sujet -> Change de sujet poliment.

{context_prompt}

RÈGLES STRICTES DE LANGUE:
- Segment "{user_lang_name}": UNIQUEMENT {user_lang_name}. Sert pour le feedback, l'explication, et la traduction de la phrase suivante.
- Segment "{learning_lang}": UNIQUEMENT {teaching_lang_name}. C'est la phrase que l'utilisateur doit entendre et pratiquer.

❌ JAMAIS d'anglais dans la réponse.
❌ JAMAIS utiliser des caractères {teaching_script} dans le segment {user_lang_name}
❌ JAMAIS utiliser des mots {teaching_lang_name} dans le segment {user_lang_name}
❌ IMPORTANT: Le champ "text" du segment "{learning_lang}" DOIT contenir du {teaching_lang_name}.
❌ IMPORTANT: Si l'utilisateur demande une traduction, fournis-la.
❌ IMPORTANT: Ne JAMAIS laisser le segment "{learning_lang}" vide.

FORMAT JSON OBLIGATOIRE:
{{
  "user_analysis": {{
    "is_correct": true,
    "corrected_text": "string (correction si nécessaire)",
    "explanation": "string (explication si nécessaire)"
  }},
  "segments": [
    {{"lang": "{native_lang}", "text": "feedback/instruction avec TRADUCTION ({user_lang_name})"}},
    {{"lang": "{learning_lang}", "text": "phrase complète à pratiquer ({teaching_lang_name} UNIQUEMENT)"}}
  ]
}}

FEEDBACK CONSTRUCTIF:
- Si correct → féliciter + passer au suivant dans la progression
- Si erreur mineure → corriger gentiment + redemander
- Si erreur majeure → revenir à un exemple simple
- Si perdu → retour aux bases (salutation)
- Si demande "encore" → consulter historique et proposer le niveau suivant

IMPORTANT:
- Si l'utilisateur fait une erreur de grammaire, CORRIGE-LA dans `user_analysis`.
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
        
        print(f"🔍 System Prompt sent to LLM:\n{system_prompt[:500]}...") # Debug log
        
        response = await self.chat(messages)
        return self._parse_response(response, native_lang, learning_lang, history)
    
    def _parse_response(self, content: str, native_lang: str, learning_lang: str, history: list = None) -> dict:
        """Parse et valide la réponse JSON du LLM"""
        try:
            # Nettoyer markdown
            content = content.replace("```json", "").replace("```", "").strip()
            
            # Common LLM typos repair
            content = content.replace('{j"', '{"') # Fix typo seen in logs
            content = content.replace('j"user', '"user')

            
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
                print(f"❌ Structure invalide (manque segments): {result}")
                return self._fallback_response("Erreur de structure", native_lang)
            
            # Ensure user_analysis exists (backward compatibility or robustness)
            if "user_analysis" not in result:
                result["user_analysis"] = {
                    "is_correct": True,
                    "corrected_text": "",
                    "explanation": ""
                }

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
            "segments": [{"lang": lang, "text": error_messages.get(lang, error_messages["fr"])}],
            "user_analysis": {
                "is_correct": True,
                "corrected_text": "",
                "explanation": ""
            }
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
        
        # 3. Compter les caractères cyrilliques vs latins
        cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        latin_count = sum(1 for c in text if c.isalpha() and not ('\u0400' <= c <= '\u04FF'))
        
        # Si majorité cyrillique ET pas de mots français → russe
        if cyrillic_count > 0 and cyrillic_count > latin_count and french_word_count == 0:
            return "ru"
            
        # 4. Check for English (Basic)
        english_words = ['the', 'is', 'hello', 'hi', 'how', 'are', 'you', 'give', 'me', 'exercise', 'learn']
        english_count = sum(1 for word in english_words if f" {word} " in f" {text_lower} ")
        if english_count >= 2 and french_word_count == 0:
            return "en"
        
        # Par défaut français (alphabet latin)
        return "fr"
    
    def _validate_response_quality(self, segments: list, native_lang: str, learning_lang: str, history: list = None) -> bool:
        """
        Valide la qualité de la réponse :
        1. Pureté des langues (pas de mélange abusk
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
        
        # Auto-repair: If one language is missing, we try to fix it instead of hard failing
        if "fr" not in langs_present:
            print(f"⚠️ Manque le segment 'fr'. Ajout d'un placeholder.")
            # Add a generic feedback segment
            segments.insert(0, {"lang": "fr", "text": "Voici la phrase à pratiquer :"})
            
        if "ru" not in langs_present:
            print(f"⚠️ Manque le segment 'ru'. Tentative de récupération ou placeholder.")
            # If we have history, maybe we can repeat the last exercise? 
            # For now, just ask to say something simple to unblock.
            segments.append({"lang": "ru", "text": "Да"}) # "Yes" - very simple placeholder to avoid crash
            
        # Re-check
        langs_present = {seg.get("lang") for seg in segments}
        if "fr" not in langs_present or "ru" not in langs_present:
             print(f"❌ ECHEC AUTO-REPAIR. Langues: {langs_present}")
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
                # We allow it if it's a request to repeat, but usually LLM shouldn't loop.
                # Let's not kill it, just warn? No, looping is bad UX.
                # Construct a variation?
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
            
            if not text or len(text) < 2 or text == "...":
                continue
            
            filename = f"{session_id}_seg{idx}_{lang}.mp3"
            filepath = f"audio_cache/{filename}"
            
            try:
                await self.generate_audio(text, lang, filepath)
                
                results.append({
                    "lang": lang,
                    "text": text,
                    "audio_url": f"/audio/{filename}"
                })
            except Exception as e:
                print(f"⚠️ TTS Error for '{text}': {e}")
                continue
        
        return results
