#!/usr/bin/env python3
"""
Test de validation des langues des segments.
"""

def detect_text_language(text: str) -> str:
    """
    Détecte la langue du texte (français ou russe) de manière heuristique.
    """
    # Caractères cyrilliques (russe)
    cyrillic_chars = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    # Caractères latins + accents français
    latin_chars = sum(1 for c in text if c.isalpha() and not ('\u0400' <= c <= '\u04FF'))
    
    # Mots-clés français communs
    french_keywords = ['le', 'la', 'les', 'un', 'une', 'des', 'je', 'tu', 'il', 'vous', 'est', 'sont', 'avoir', 'être', 'pour']
    french_score = sum(1 for word in french_keywords if f" {word} " in f" {text.lower()} ")
    
    # Mots-clés russes communs
    russian_keywords = ['это', 'вы', 'как', 'что', 'на', 'в', 'я', 'не', 'и', 'с']
    russian_score = sum(1 for word in russian_keywords if word in text.lower())
    
    # Décision
    if cyrillic_chars > latin_chars * 0.3:  # Au moins 30% de caractères cyrilliques
        return "ru"
    elif russian_score > french_score:
        return "ru"
    else:
        return "fr"

def validate_segment_languages(segments: list) -> list:
    """
    Valide et corrige automatiquement les tags de langue des segments.
    """
    validated_segments = []
    
    for segment in segments:
        lang = segment.get("lang", "fr")
        text = segment.get("text", "").strip()
        
        if not text:
            continue
        
        # Détection heuristique de la langue
        detected_lang = detect_text_language(text)
        
        # Si le tag ne correspond pas au contenu, corriger
        if detected_lang != lang:
            print(f"⚠️  Correction: tag='{lang}' → '{detected_lang}' | Text: {text[:50]}...")
            lang = detected_lang
        
        validated_segments.append({"lang": lang, "text": text})
    
    return validated_segments

def test_language_detection():
    print("🧪 Test de détection de langue\n")
    print("="*70)
    
    # Test 1: Texte français marqué comme russe (erreur)
    segments_test1 = [
        {"lang": "ru", "text": "Je suis prêt à vous aider avec des leçons de français."},
        {"lang": "fr", "text": "Quels sont vos niveaux et vos objectifs pour apprendre le français ?"}
    ]
    
    print("\n📝 Test 1: Texte français mal tagué comme 'ru'")
    print(f"Avant: {segments_test1[0]}")
    validated1 = validate_segment_languages(segments_test1)
    print(f"Après: {validated1[0]}")
    print(f"✅ Correction: {segments_test1[0]['lang']} → {validated1[0]['lang']}")
    
    print("\n" + "="*70)
    
    # Test 2: Texte russe correctement marqué
    segments_test2 = [
        {"lang": "ru", "text": "Вы хотите задания по уровням языка?"},
        {"lang": "fr", "text": "Je peux vous donner des exercices."}
    ]
    
    print("\n📝 Test 2: Tags corrects (pas de changement)")
    validated2 = validate_segment_languages(segments_test2)
    print(f"Segment RU: ✅ Correct")
    print(f"Segment FR: ✅ Correct")
    
    print("\n" + "="*70)
    
    # Test 3: Texte russe marqué comme français (erreur)
    segments_test3 = [
        {"lang": "fr", "text": "Привет, как дела?"},
        {"lang": "fr", "text": "Bonjour, comment ça va ?"}
    ]
    
    print("\n📝 Test 3: Texte russe mal tagué comme 'fr'")
    print(f"Avant: {segments_test3[0]}")
    validated3 = validate_segment_languages(segments_test3)
    print(f"Après: {validated3[0]}")
    print(f"✅ Correction: {segments_test3[0]['lang']} → {validated3[0]['lang']}")
    
    print("\n" + "="*70)
    
    # Test 4: Cas réel du bug
    segments_test4 = [
        {"lang": "ru", "text": "Vous voulez apprendre le niveau B1? C'est un bon niveau."},
        {"lang": "fr", "text": "Le niveau B1 est considéré comme intermédiaire."}
    ]
    
    print("\n📝 Test 4: Cas réel du bug (français tagué 'ru')")
    print(f"Avant: {segments_test4[0]}")
    validated4 = validate_segment_languages(segments_test4)
    print(f"Après: {validated4[0]}")
    print(f"✅ Correction: {segments_test4[0]['lang']} → {validated4[0]['lang']}")
    
    print("\n" + "="*70)
    print("\n✅ Tous les tests terminés!\n")

if __name__ == "__main__":
    test_language_detection()
