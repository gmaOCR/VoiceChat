import os
import httpx
import json
import asyncio
import edge_tts
import tempfile

# Configuration
OLLAMA_URL = "http://192.168.1.28:11434"
MODEL_NAME = "llama3.1:8b"
WHISPER_API_URL = "http://mars.gregorymariani.com:8001"

class STTService:
    def __init__(self):
        self.api_url = WHISPER_API_URL
        print(f"Using remote Whisper API: {self.api_url}")

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
        Analyzes the user text, detects language, and generates segmented response.
        Returns a dict with 'detected_input_lang', 'correction', and 'segments'.
        """
        
        # Determine languages
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

        # Construct System Prompt - INSTRUCTEUR VOCAL
        system_prompt = (
            f"Tu es un PROFESSEUR DE LANGUE VOCAL {learning_lang_name}.\n"
            f"L'utilisateur PARLE (audio) - il ne voit RIEN, il ÉCOUTE ta réponse.\n"
            f"Langue native: {native_lang_name} | Langue apprentissage: {learning_lang_name}\n\n"
            
            "🎙️ MODE VOCAL UNIQUEMENT 🎙️\n"
            "• PAS de ponctuation markdown (**, *, `, etc.)\n"
            "• PAS de formatage (pas de \\n, pas de liste)\n"
            "• PAS de métadonnées (pas de 'lang:', 'Segment', etc.)\n"
            "• PAS d'instructions écrites (pas de 'répétez', 'écrivez')\n"
            "• Phrases COURTES et NATURELLES comme à l'oral\n"
            "• Pas de ponctuation excessive (!, ?, ...)\n\n"
            
            "🔍 DÉTECTION DE LANGUE (ANALYSE LE TEXTE) 🔍\n"
            f"Analyse UNIQUEMENT le texte de l'utilisateur:\n"
            f"• Si texte contient des mots {learning_lang_name} (cyrillique pour RU) → detected_input_lang = '{learning_lang}'\n"
            f"• Si texte contient des mots {native_lang_name} (latin pour FR) → detected_input_lang = '{native_lang}'\n"
            f"• Exemples FR: 'comment', 'dit-on', 'je', 'veux' → detected = '{native_lang}'\n"
            f"• Exemples RU: 'привет', 'как', 'дела' → detected = '{learning_lang}'\n\n"
            
            "📋 RÈGLES DE RÉPONSE 📋\n"
            f"CAS 1: L'utilisateur PRATIQUE le {learning_lang_name} (texte en {learning_lang_name}):\n"
            f"  Segment 1 [{native_lang}]: 'Très bien' ou 'Attention à la prononciation' (1 phrase)\n"
            f"  Segment 2 [{learning_lang}]: Une nouvelle phrase à répéter\n\n"
            
            f"CAS 2: L'utilisateur DEMANDE de l'aide (texte en {native_lang_name}):\n"
            f"  Segment 1 [{native_lang}]: Réponse directe courte (max 2 phrases)\n"
            f"  Segment 2 [{learning_lang}]: L'expression demandée en {learning_lang_name}\n\n"
            
            "💬 EXEMPLES DE RÉPONSES VOCALES 💬\n"
            f"Question: 'Comment dit-on bonjour en russe'\n"
            f"✅ Segment 1 [fr]: En russe on dit\n"
            f"✅ Segment 2 [ru]: Здравствуйте\n\n"
            
            f"Question: 'Привет'\n"
            f"✅ Segment 1 [ru]: Отлично\n"
            f"✅ Segment 2 [ru]: Повторите Как дела\n\n"
            
            "🚫 INTERDICTIONS ABSOLUES 🚫\n"
            "• JAMAIS de markdown: pas de **, *, `, ##\n"
            "• JAMAIS de liste: pas de 1., 2., •, -\n"
            "• JAMAIS de retour ligne: pas de \\n\n"
            "• JAMAIS de métadonnées: pas de 'Langue:', 'Résultat:', etc.\n"
            "• JAMAIS de parenthèses explicatives: (ceci est...)\n"
            "• JAMAIS d'instructions: 'répétez', 'écrivez', 'attention'\n\n"
            
            "📤 FORMAT JSON OBLIGATOIRE 📤\n"
            "{\n"
            f'  "detected_input_lang": "{native_lang}" ou "{learning_lang}",\n'
            f'  "correction": "" (vide si pas erreur),\n'
            '  "segments": [\n'
            f'    {{"lang": "{native_lang}", "text": "phrase courte naturelle"}},\n'
            f'    {{"lang": "{learning_lang}", "text": "phrase courte naturelle"}}\n'
            '  ]\n'
            "}\n\n"
            
            "⚡ RÈGLES CRITIQUES ⚡\n"
            f"1. Un segment 'lang': '{native_lang}' = 100% {native_lang_name}\n"
            f"2. Un segment 'lang': '{learning_lang}' = 100% {learning_lang_name}\n"
            "3. Texte PARLÉ uniquement, pas écrit\n"
            "4. Phrases SIMPLES, COURTES (max 10 mots)\n"
            "5. Pas de ponctuation markdown\n"
            "6. Détection langue basée sur le CONTENU du texte"
        )
        
        user_msg = f"Phrase de l'utilisateur: {user_text}"

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
                result = json.loads(json_str)
                
                # Validate structure
                if "detected_input_lang" not in result:
                    result["detected_input_lang"] = target_lang
                if "correction" not in result:
                    result["correction"] = ""
                if "segments" not in result or not isinstance(result["segments"], list):
                    # Fallback: create single segment
                    result["segments"] = [{"lang": target_lang, "text": content}]
                
                # VALIDATION CRITIQUE: Vérifier que le tag de langue correspond au contenu
                result["segments"] = self._validate_segment_languages(result["segments"])
                
                return result
            else:
                # Fallback if JSON parsing fails
                return {
                    "detected_input_lang": target_lang,
                    "correction": "",
                    "segments": [{"lang": target_lang, "text": content}]
                }
        except Exception as e:
            print(f"JSON Parse Error: {e} | Content: {content}")
            return {
                "detected_input_lang": target_lang,
                "correction": "",
                "segments": [{"lang": target_lang, "text": "Erreur de traitement de la réponse IA."}]
            }
    
    def _validate_segment_languages(self, segments: list) -> list:
        """
        Valide et corrige automatiquement les tags de langue des segments.
        Détecte si le contenu est en français ou en russe et ajuste le tag.
        """
        validated_segments = []
        
        for segment in segments:
            lang = segment.get("lang", "fr")
            text = segment.get("text", "").strip()
            
            if not text:
                continue
            
            # Détection heuristique de la langue
            detected_lang = self._detect_text_language(text)
            
            # Si le tag ne correspond pas au contenu, corriger
            if detected_lang != lang:
                print(f"⚠️  Language mismatch corrected: tag='{lang}' but content is '{detected_lang}' → Text: {text[:50]}...")
                lang = detected_lang
            
            validated_segments.append({"lang": lang, "text": text})
        
        return validated_segments
    
    def _detect_text_language(self, text: str) -> str:
        """
        Détecte la langue du texte (français ou russe) de manière heuristique améliorée.
        """
        text_lower = text.lower()
        
        # Caractères cyrilliques (russe)
        cyrillic_chars = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        # Caractères latins
        latin_chars = sum(1 for c in text if c.isalpha() and not ('\u0400' <= c <= '\u04FF'))
        
        # Si plus de 5 caractères cyrilliques, c'est probablement du russe
        if cyrillic_chars > 5:
            return "ru"
        
        # Si au moins 1 caractère cyrillique, c'est du russe
        if cyrillic_chars > 0:
            return "ru"
        
        # Mots-clés français TRÈS communs (mots fonctionnels)
        french_keywords = [
            'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du',
            'je', 'tu', 'il', 'elle', 'nous', 'vous', 'ils', 'elles',
            'est', 'sont', 'être', 'avoir', 'a', 'ai', 'as', 'ont',
            'ce', 'cette', 'ces', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes',
            'comment', 'dit', 'on', 'dit-on', 'en', 'pour', 'avec', 'dans',
            'au', 'aux', 'à', 'ou', 'et', 'mais', 'ou', 'donc'
        ]
        
        # Vérification stricte des mots français
        french_score = sum(2 if f" {word} " in f" {text_lower} " else 
                          (1 if text_lower.startswith(word + " ") or text_lower.endswith(" " + word) else 0)
                          for word in french_keywords)
        
        # Patterns français typiques
        french_patterns = ['dit-on', "qu'", "c'est", "n'", "d'", "l'", 'ç']
        french_pattern_score = sum(3 for pattern in french_patterns if pattern in text_lower)
        
        # Score total français
        total_french_score = french_score + french_pattern_score
        
        # Mots russes translittérés ou empruntés (cas particuliers)
        # Si on détecte des mots français typiques, c'est du français
        if total_french_score >= 3:  # Au moins 3 points de score français
            return "fr"
        
        # Si beaucoup de caractères latins et aucun mot français, c'est suspect
        # mais par défaut on considère que c'est du français (langue par défaut)
        if latin_chars > 0:
            return "fr"
        
        # Fallback: français par défaut
        return "fr"

class TTSService:
    def _clean_text_for_speech(self, text: str) -> str:
        """
        Nettoie le texte pour le rendre adapté à la synthèse vocale.
        Enlève le markdown et les artefacts qui seraient lus à voix haute.
        """
        import re
        
        # Enlever le markdown
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *italic*
        text = re.sub(r'`([^`]+)`', r'\1', text)        # `code`
        text = re.sub(r'#+\s*([^\n]+)', r'\1', text)    # ## headers → garder contenu
        
        # Enlever les bullets et numérotations
        text = re.sub(r'^\s*[\-\*•]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        
        # Enlever les parenthèses explicatives qui polluent
        text = re.sub(r'\([^)]*\)', '', text)
        
        # Enlever les métadonnées type "Langue:", "Résultat:", "Segment X:", etc.
        text = re.sub(r'\b(Langue|Lang|Résultat|Attendu|Segment\s*\d*)\s*:\s*', '', text, flags=re.IGNORECASE)
        
        # Enlever les backticks et quotes
        text = text.replace('`', '').replace("'", "'")
        
        # Remplacer plusieurs espaces par un seul
        text = re.sub(r'\s+', ' ', text)
        
        # Enlever les retours à la ligne multiples
        text = re.sub(r'\n\s*\n', '. ', text)
        text = text.replace('\n', ' ')
        
        return text.strip()
    
    async def generate_audio(self, text: str, language: str, output_file: str):
        # Nettoyer le texte avant TTS
        clean_text = self._clean_text_for_speech(text)
        
        # Select voice based on language
        voice = "fr-FR-VivienneMultilingualNeural" if language == "fr" else "ru-RU-SvetlanaNeural"
        
        communicate = edge_tts.Communicate(clean_text, voice)
        await communicate.save(output_file)
    
    async def generate_segmented_audio(self, segments: list, session_id: str) -> list:
        """
        Generate separate audio files for each language segment.
        Returns list of dicts with {lang, audio_url}.
        """
        audio_urls = []
        
        for idx, segment in enumerate(segments):
            lang = segment.get("lang", "fr")
            text = segment.get("text", "").strip()
            
            if not text:
                continue
            
            audio_filename = f"{session_id}_segment_{idx}_{lang}.mp3"
            audio_path = f"audio_cache/{audio_filename}"
            
            await self.generate_audio(text, lang, audio_path)
            
            audio_urls.append({
                "lang": lang,
                "text": text,
                "audio_url": f"/audio/{audio_filename}"
            })
        
        return audio_urls

