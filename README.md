# 🎓 VoiceChat - Apprentissage Bilingue Vocal

Application d'apprentissage de langues par conversation vocale interactive avec IA.

## 🌟 Fonctionnalités

- **Apprentissage bilingue naturel** : L'IA répond dans votre langue maternelle et vous fait pratiquer dans la langue cible
- **Reconnaissance vocale** : Whisper large-v3-turbo (GPU distant)
- **IA pédagogue** : LLM adapté au contexte d'apprentissage
- **Synthèse vocale** : TTS natif en français et russe
- **Réponses segmentées** : Audio multilingue pour une immersion progressive

## 🎯 Principe

**Étudiant français apprenant le russe** :
- Vous demandez en français → L'IA explique en français + exemples en russe
- Vous pratiquez en russe → L'IA donne feedback en français + correction en russe

**C'est comme avoir un professeur bilingue qui s'adapte à vous !**

## 🏗️ Architecture

```
Frontend (HTML/JS)
    ↓ [audio + langues]
Backend FastAPI
    ↓ transcription
Whisper API (mars.gregorymariani.com:8001)
    ↓ texte utilisateur
LLM Mistral (Ollama local)
    ↓ segments bilingues
TTS Edge-TTS
    ↓ fichiers audio
Frontend
    ↓ lecture séquentielle
```

## 🚀 Installation

```bash
# Cloner le projet
git clone [repo-url]
cd VoiceChat

# Créer environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer dépendances
pip install -r requirements.txt

# Lancer l'application
python main.py
```

Accès : http://localhost:8000

## ⚙️ Configuration

### Services Requis

1. **Ollama** (LLM local) : `http://192.168.1.28:11434`
   - Modèle : `mistral:latest`
   
2. **Whisper API** (distant) : `http://mars.gregorymariani.com:8001`
   - Modèle : `openai/whisper-large-v3-turbo`

### Variables (services.py)

```python
OLLAMA_URL = "http://192.168.1.28:11434"
MODEL_NAME = "mistral:latest"
WHISPER_API_URL = "http://mars.gregorymariani.com:8001"
```

## 📋 API

### POST /chat

**Request**
```json
{
  "audio": "fichier.webm",
  "source_lang": "fr",    // Langue maternelle
  "target_lang": "ru"     // Langue à apprendre
}
```

**Response**
```json
{
  "user_text": "Comment dit-on bonjour",
  "segments": [
    {"lang": "fr", "text": "En russe on dit"},
    {"lang": "ru", "text": "Здравствуйте"}
  ],
  "audio_segments": [
    {"lang": "fr", "audio_url": "/audio/xxx_seg0_fr.mp3"},
    {"lang": "ru", "audio_url": "/audio/xxx_seg1_ru.mp3"}
  ]
}
```

## 📊 Performance

| Étape | Temps | Optimisations |
|-------|-------|---------------|
| Upload audio | ~0.05s | - |
| STT (Whisper) | ~2s | GPU distant |
| LLM (Mistral) | ~3-4s | Prompt optimisé (-56% tokens) |
| TTS (Edge) | ~1-2s | - |
| **TOTAL** | **~6-8s** | -40% vs version initiale |

## 🧹 Code Qualité

- **260 lignes** de code total (vs 437 avant refactorisation)
- **-40% de complexité** sur les fonctions critiques
- **Prompt -57%** plus court et clair
- **0 erreurs** de linting

## 🎓 Exemples d'Usage

### Cas 1 : Question en français
```
🎤 "Comment dit-on au revoir en russe"

🔊 [FR] "En russe on dit"
🔊 [RU] "До свидания"
🔊 [FR] "C'est formel et poli"
```

### Cas 2 : Pratique en russe
```
🎤 "Доброе утро"

🔊 [FR] "Parfait"
🔊 [RU] "Как дела"
🔊 [FR] "Maintenant demande comment ça va"
```

## 🛠️ Développement

### Structure des Fichiers

```
VoiceChat/
├── main.py              # API FastAPI
├── services.py          # STT, LLM, TTS
├── whisper_server.py    # Serveur Whisper distant
├── requirements.txt     # Dépendances Python
├── static/
│   ├── index.html       # Interface utilisateur
│   ├── app.js           # Logique frontend
│   └── style.css        # Styles
├── audio_cache/         # Fichiers MP3 générés
└── temp_uploads/        # Upload temporaire
```

### Tests

```bash
# Tester serveur Whisper
python test_whisper_server.py

# Tester l'application complète
# 1. Lancer main.py
# 2. Ouvrir http://localhost:8000
# 3. Parler dans le micro
```

## 📚 Documentation

- **REFACTORING_BILINGUE.md** : Détails de la refactorisation et logique pédagogique

## 🤝 Contribution

Améliorations futures possibles :
- Support d'autres langues (ES, DE, IT...)
- Mode streaming pour réponses plus rapides
- Cache LLM pour questions fréquentes
- Interface mobile responsive

## 📄 Licence

[Votre licence ici]

---

**Note** : Ce projet nécessite un serveur Ollama local et un serveur Whisper distant pour fonctionner. - AI Language Tutor 🎓🗣️

> Chatbot vocal multilingue intelligent avec segmentation audio et détection de langue automatique

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🌟 Caractéristiques Principales

### 🎯 Segmentation Audio Multilingue
- **Détection automatique** de la langue d'input (français/russe)
- **Génération audio segmentée** : chaque langue utilise sa propre voix native
- **Lecture séquentielle** fluide des segments audio
- **Pas de répétition** inutile de l'input utilisateur

### 🧠 Intelligence Artificielle
- **STT (Speech-to-Text)** : Whisper (OpenAI)
- **LLM** : Llama 3.1 8B (via Ollama)
- **TTS (Text-to-Speech)** : Edge-TTS (voix natives FR/RU)

### 🎨 Interface Utilisateur
- **Design moderne** : Mode sombre élégant
- **Indicateurs visuels** : Drapeaux et noms de langue colorés
- **Enregistrement simple** : Maintenir le bouton pour parler
- **Responsive** : Fonctionne sur mobile et desktop

---

## 🚀 Démarrage Rapide

### Prérequis
- Python 3.8+
- Ollama installé et configuré
- Microphone fonctionnel

### Installation

```bash
# Cloner le projet
git clone https://github.com/gmaOCR/VoiceChat.git
cd VoiceChat

# Installer les dépendances
pip install -r requirements.txt

# Lancer le serveur
python main.py
```

### Accès
Ouvrir votre navigateur à : **http://localhost:8000**

---

## 📖 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Guide d'utilisation complet
- **[IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md)** - Architecture technique
- **[CHANGELOG.md](CHANGELOG.md)** - Historique des versions

---

## 🎯 Cas d'Usage

### Scénario 1 : Pratiquer le Français
**Vous :** 🇷🇺 (Native) | **Cible :** 🇫🇷 (Apprentissage)

**Vous dites :** _"Bonjour, comment ça va ?"_

**AI répond :**
- 🇷🇺 Отлично! Вы сказали это правильно.
- 🇫🇷 Ça va bien, merci ! Et vous ?

**Audio :** 🔊 Voix russe → 🔊 Voix française

---

### Scénario 2 : Demander de l'Aide
**Vous dites :** _"Как спросить, где находится вокзал?"_ (en russe)

**AI répond :**
- 🇷🇺 Чтобы спросить где находится вокзал, скажите...
- 🇫🇷 Où est la gare ?

**Audio :** 🔊 Explication en russe → 🔊 Exemple en français

---

## 🏗️ Architecture

```
┌─────────────┐
│ Utilisateur │ Parle (Audio)
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Whisper (STT)  │ Transcription
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│   Ollama (LLM)      │ Détection langue + Génération segments
│   Llama 3.1 8B      │
└────────┬────────────┘
         │
         ▼
    ┌────────────────────┐
    │ segments: [        │
    │   {lang: ru, ...}  │
    │   {lang: fr, ...}  │
    │ ]                  │
    └─────┬──────────────┘
          │
          ▼
┌─────────────────────────┐
│  Edge-TTS               │
│  ├─ segment_0_ru.mp3   │ ← Voix russe
│  └─ segment_1_fr.mp3   │ ← Voix française
└──────────┬──────────────┘
           │
           ▼
    ┌──────────────┐
    │   Frontend   │ Lecture séquentielle
    └──────────────┘
```

---

## 🛠️ Technologies

| Composant | Technologie | Rôle |
|---|---|---|
| **Backend** | FastAPI | API REST |
| **STT** | Faster-Whisper | Transcription audio |
| **LLM** | Ollama (Llama 3.1) | Correction & Réponse IA |
| **TTS** | Edge-TTS | Génération audio |
| **Frontend** | Vanilla JS | Interface utilisateur |
| **Styling** | CSS3 | Design moderne |

---

## 📊 Structure du Projet

```
VoiceChat/
├── main.py                    # Serveur FastAPI
├── services.py                # Services STT/LLM/TTS
├── test_segmentation.py       # Tests unitaires
├── requirements.txt           # Dépendances Python
│
├── static/
│   ├── index.html             # Interface utilisateur
│   ├── app.js                 # Logique frontend
│   └── style.css              # Styles
│
├── audio_cache/               # Fichiers audio générés
├── temp_uploads/              # Uploads temporaires
│
├── QUICKSTART.md              # Guide utilisateur
├── IMPLEMENTATION_NOTES.md    # Documentation technique
├── CHANGELOG.md               # Historique versions
└── README.md                  # Ce fichier
```

---

## 🧪 Tests

### Test Manuel
```bash
# Lancer le serveur
python main.py

# Dans un autre terminal
python test_segmentation.py
```

### Vérification
- ✅ Détection de langue fonctionne
- ✅ Segments générés correctement
- ✅ Audio créé pour chaque segment
- ✅ Lecture séquentielle fluide

---

## 🎨 Aperçu

### Interface Principale
```
┌───────────────────────────────────────┐
│        Voice Chatbot                  │
│                                       │
│  🇫🇷 Je parle Français (Apprendre Russe) │
│  🇷🇺 Я говорю по-русски (Apprendre Français) │
│                                       │
├───────────────────────────────────────┤
│                                       │
│  User: Bonjour, comment ça va ?       │
│                                       │
│  ✓ Correction: [si nécessaire]        │
│                                       │
│  🇷🇺 Русский: Отлично!                │
│  🇫🇷 Français: Ça va bien, merci !    │
│                                       │
├───────────────────────────────────────┤
│            🎙️                         │
│          Prêt                         │
└───────────────────────────────────────┘
```

---

## 🔧 Configuration

### Changer le Modèle LLM
Éditer `services.py` :
```python
MODEL_NAME = "mistral:latest"  # ou autre modèle
```

### Changer les Voix TTS
Éditer `services.py` :
```python
voice = "fr-FR-DeniseNeural" if language == "fr" else "ru-RU-DmitryNeural"
```

Liste des voix disponibles :
```bash
edge-tts --list-voices | grep -E "fr-FR|ru-RU"
```

### Configurer Ollama
Éditer `services.py` :
```python
OLLAMA_URL = "http://localhost:11434"  # Votre URL Ollama
```

---

## 🐛 Dépannage

### Problème : Audio ne se génère pas
**Solution :** Vérifier que `edge-tts` fonctionne
```bash
edge-tts --text "Test" --voice fr-FR-DeniseNeural --write-media test.mp3
```

### Problème : LLM ne répond pas
**Solution :** Vérifier la connexion Ollama
```bash
curl http://localhost:11434/api/tags
```

### Problème : Microphone non détecté
**Solution :** Autoriser l'accès micro dans le navigateur (HTTPS requis en production)

---

## 📈 Roadmap

### v2.1 (Court Terme)
- [ ] Cache des réponses fréquentes
- [ ] Nettoyage automatique audio_cache/
- [ ] Export de conversations

### v3.0 (Moyen Terme)
- [ ] Support multi-langues (ES, DE, IT, ZH)
- [ ] Persistance de conversation
- [ ] Statistiques de progression

### v4.0 (Long Terme)
- [ ] Mode hors-ligne complet
- [ ] Application mobile native
- [ ] Gamification de l'apprentissage

---

## 🤝 Contribution

Les contributions sont les bienvenues ! Voici comment participer :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit vos changements (`git commit -m 'Add AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

---

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 👨‍💻 Auteur

**gmaOCR**
- GitHub: [@gmaOCR](https://github.com/gmaOCR)

---

## 🙏 Remerciements

- [OpenAI Whisper](https://github.com/openai/whisper) - STT
- [Ollama](https://ollama.ai/) - LLM local
- [Edge-TTS](https://github.com/rany2/edge-tts) - TTS gratuit
- [FastAPI](https://fastapi.tiangolo.com/) - Framework web moderne

---

## 📝 Notes

### Performances
- **Latence typique** : 3-5 secondes (STT + LLM + TTS)
- **Précision STT** : >90% pour audio clair
- **Qualité TTS** : Voix naturelles natives

### Limitations Connues
- Nécessite connexion internet (STT, LLM, TTS)
- Supporte uniquement FR/RU actuellement
- Pas de persistance de session

### Améliorations vs Précédentes Versions
- ✅ **Audio segmenté** : Voix appropriées par langue
- ✅ **Pas de répétition** : Input utilisateur non vocalisé
- ✅ **Indicateurs visuels** : Drapeaux et couleurs
- ✅ **Architecture propre** : Code modulaire et testable

---

**⭐ N'oubliez pas de donner une étoile si ce projet vous aide ! ⭐**
