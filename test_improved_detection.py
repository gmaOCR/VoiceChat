#!/usr/bin/env python3
"""
Test de détection de langue améliorée et nettoyage de texte.
"""
import re

def detect_text_language(text: str) -> str:
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
    
    # Mots-clés français TRÈS communs
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
    
    # Si on détecte des mots français typiques, c'est du français
    if total_french_score >= 3:
        return "fr"
    
    # Si beaucoup de caractères latins et aucun mot français, c'est suspect
    # mais par défaut on considère que c'est du français
    if latin_chars > 0:
        return "fr"
    
    # Fallback: français par défaut
    return "fr"

def clean_text_for_speech(text: str) -> str:
    """
    Nettoie le texte pour le rendre adapté à la synthèse vocale.
    """
    # Enlever le markdown
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *italic*
    text = re.sub(r'`([^`]+)`', r'\1', text)        # `code`
    text = re.sub(r'#+\s*', '', text)               # ## headers
    
    # Enlever les bullets et numérotations
    text = re.sub(r'^\s*[\-\*•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Enlever les parenthèses explicatives
    text = re.sub(r'\([^)]*\)', '', text)
    
    # Enlever les métadonnées
    text = re.sub(r'\b(Langue|Lang|Résultat|Attendu|Segment)\s*:\s*', '', text, flags=re.IGNORECASE)
    
    # Enlever les backticks et quotes
    text = text.replace('`', '').replace("'", "'")
    
    # Remplacer plusieurs espaces par un seul
    text = re.sub(r'\s+', ' ', text)
    
    # Enlever les retours à la ligne multiples
    text = re.sub(r'\n\s*\n', '. ', text)
    text = text.replace('\n', ' ')
    
    return text.strip()

def test_detection():
    print("🧪 Test de détection de langue améliorée\n")
    print("="*70)
    
    tests = [
        ("Comment dit-on au revoir en russe ?", "fr", "Question typique française"),
        ("Comment dit-on bonjour", "fr", "Question simple"),
        ("Je veux apprendre le russe", "fr", "Phrase française"),
        ("Привет", "ru", "Mot russe seul"),
        ("Здравствуйте как дела", "ru", "Phrase russe"),
        ("Bonjour comment ça va", "fr", "Salutation française"),
        ("dit-on", "fr", "Expression française typique"),
        ("qu'est-ce que c'est", "fr", "Expression avec apostrophes"),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected, description in tests:
        detected = detect_text_language(text)
        status = "✅" if detected == expected else "❌"
        
        if detected == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} {description}")
        print(f"   Texte: '{text}'")
        print(f"   Attendu: {expected} | Détecté: {detected}")
        print()
    
    print("="*70)
    print(f"\n📊 Résultats: {passed} succès, {failed} échecs")

def test_cleaning():
    print("\n" + "="*70)
    print("🧪 Test de nettoyage de texte pour TTS\n")
    
    tests = [
        ("**Niveau A2**", "Niveau A2", "Bold markdown"),
        ("Répétez: `Здравствуйте`", "Répétez: Здравствуйте", "Code markdown"),
        ("Bienvenue !\n\nJe détecte", "Bienvenue ! Je détecte", "Retours ligne"),
        ("Langue: `fr`", "fr", "Métadonnées"),
        ("(ceci est un exemple)", "", "Parenthèses explicatives"),
        ("## Titre\nContenu", "Contenu", "Headers markdown"),
        ("* Item 1\n* Item 2", "Item 1 Item 2", "Liste"),
        ("Segment 1: Bonjour", "Bonjour", "Métadonnée Segment"),
    ]
    
    for original, expected, description in tests:
        cleaned = clean_text_for_speech(original)
        status = "✅" if cleaned == expected else "⚠️"
        
        print(f"{status} {description}")
        print(f"   Original: '{original}'")
        print(f"   Nettoyé : '{cleaned}'")
        if cleaned != expected:
            print(f"   Attendu : '{expected}'")
        print()
    
    print("="*70)

if __name__ == "__main__":
    test_detection()
    test_cleaning()
    print("\n✅ Tests terminés!\n")
