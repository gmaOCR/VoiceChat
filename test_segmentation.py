#!/usr/bin/env python3
"""
Script de test pour vérifier la segmentation audio multilingue.
"""
import asyncio
import json
from services import LLMService, TTSService

async def test_segmentation():
    print("=== Test de Segmentation Audio Multilingue ===\n")
    
    llm = LLMService()
    tts = TTSService()
    
    # Scénario 1 : Utilisateur parle français (pratique)
    print("📝 Scénario 1 : Pratique en français")
    result1 = await llm.correct_and_respond(
        user_text="Bonjour, comment allez-vous?",
        source_lang="fr",
        target_lang="ru"
    )
    print(f"Detected lang: {result1.get('detected_input_lang')}")
    print(f"Correction: {result1.get('correction')}")
    print(f"Segments: {json.dumps(result1.get('segments'), ensure_ascii=False, indent=2)}")
    print()
    
    # Scénario 2 : Utilisateur demande de l'aide en russe
    print("📝 Scénario 2 : Demande d'aide en russe")
    result2 = await llm.correct_and_respond(
        user_text="Как сказать 'привет' по-французски?",
        source_lang="ru",
        target_lang="fr"
    )
    print(f"Detected lang: {result2.get('detected_input_lang')}")
    print(f"Correction: {result2.get('correction')}")
    print(f"Segments: {json.dumps(result2.get('segments'), ensure_ascii=False, indent=2)}")
    print()
    
    # Test génération audio segmentée
    print("🎵 Test génération audio segmentée...")
    test_segments = [
        {"lang": "fr", "text": "Bonjour, ceci est un test en français."},
        {"lang": "ru", "text": "Привет, это тест на русском языке."}
    ]
    
    audio_urls = await tts.generate_segmented_audio(test_segments, "test_session")
    print(f"Audio généré: {len(audio_urls)} segments")
    for i, seg in enumerate(audio_urls):
        print(f"  Segment {i+1} [{seg['lang']}]: {seg['audio_url']}")
    
    print("\n✅ Tests terminés avec succès!")

if __name__ == "__main__":
    asyncio.run(test_segmentation())
