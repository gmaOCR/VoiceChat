#!/usr/bin/env python3
"""Test manuel simple de la logique bilingue"""

import asyncio
import sys
from services import LLMService

async def test_lesson():
    llm = LLMService()
    
    tests = [
        {
            "input": "Comment dit-on bonjour en russe",
            "native": "fr",
            "learning": "ru",
            "desc": "Question FR → Réponse FR + exemple RU"
        },
        {
            "input": "Привет",
            "native": "fr", 
            "learning": "ru",
            "desc": "Pratique RU → Feedback FR + correction RU"
        },
        {
            "input": "Что такое спасибо по французски",
            "native": "ru",
            "learning": "fr", 
            "desc": "Russe apprenant français"
        }
    ]
    
    print("=" * 70)
    print("🧪 TEST LOGIQUE BILINGUE")
    print("=" * 70)
    
    for i, test in enumerate(tests, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}: {test['desc']}")
        print(f"{'='*70}")
        print(f"📝 Input: {test['input']}")
        print(f"🏠 Native: {test['native']} | 📚 Learning: {test['learning']}")
        print()
        
        try:
            result = await llm.generate_lesson(
                test['input'],
                test['native'],
                test['learning']
            )
            
            segments = result.get('segments', [])
            
            if not segments:
                print("❌ Aucun segment généré")
                continue
            
            print(f"✅ {len(segments)} segments générés:")
            for j, seg in enumerate(segments, 1):
                lang = seg['lang']
                text = seg['text']
                flag = "🇫🇷" if lang == "fr" else "🇷🇺"
                print(f"  {j}. {flag} [{lang}] {text}")
            
            # Validation
            expected_langs = {test['native'], test['learning']}
            actual_langs = {seg['lang'] for seg in segments}
            
            if actual_langs.issubset(expected_langs):
                print("✅ Langues correctes")
            else:
                print(f"⚠️  Langues inattendues: {actual_langs - expected_langs}")
                
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    print("\n" + "=" * 70)
    print("✅ Tests terminés")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_lesson())
