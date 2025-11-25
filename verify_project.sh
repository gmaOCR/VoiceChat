#!/bin/bash

# Script de vérification complète du projet VoiceChat

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║     🔍 VÉRIFICATION DU PROJET VOICECHAT 🔍                ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SUCCESS=0
FAILED=0

check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✅ $1 est installé${NC}"
        ((SUCCESS++))
    else
        echo -e "${RED}❌ $1 n'est pas installé${NC}"
        ((FAILED++))
    fi
}

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅ $1 existe${NC}"
        ((SUCCESS++))
    else
        echo -e "${RED}❌ $1 manquant${NC}"
        ((FAILED++))
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✅ $1/ existe${NC}"
        ((SUCCESS++))
    else
        echo -e "${RED}❌ $1/ manquant${NC}"
        ((FAILED++))
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📦 Vérification des Dépendances Système"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_command python3
check_command pip
check_command curl
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📄 Vérification des Fichiers du Projet"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "main.py"
check_file "services.py"
check_file "test_segmentation.py"
check_file "requirements.txt"
check_file "static/index.html"
check_file "static/app.js"
check_file "static/style.css"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📁 Vérification des Dossiers"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_dir "static"
check_dir "audio_cache"
check_dir "temp_uploads"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📘 Vérification de la Documentation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "README.md"
check_file "QUICKSTART.md"
check_file "IMPLEMENTATION_NOTES.md"
check_file "CHANGELOG.md"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🐍 Vérification de la Syntaxe Python"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if python3 -m py_compile main.py services.py test_segmentation.py 2>/dev/null; then
    echo -e "${GREEN}✅ Tous les fichiers Python sont syntaxiquement corrects${NC}"
    ((SUCCESS++))
else
    echo -e "${RED}❌ Erreurs de syntaxe détectées${NC}"
    ((FAILED++))
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔌 Vérification de la Connexion Ollama"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if curl -s http://192.168.1.28:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama est accessible${NC}"
    ((SUCCESS++))
else
    echo -e "${YELLOW}⚠️  Ollama n'est pas accessible (vérifiez l'URL dans services.py)${NC}"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📊 Statistiques du Code"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Lignes Python    : $(cat main.py services.py test_segmentation.py 2>/dev/null | wc -l)"
echo "  Lignes JavaScript: $(cat static/app.js 2>/dev/null | wc -l)"
echo "  Lignes HTML      : $(cat static/index.html 2>/dev/null | wc -l)"
echo "  Lignes CSS       : $(cat static/style.css 2>/dev/null | wc -l)"
echo "  Documentation    : $(ls -1 *.md 2>/dev/null | wc -l) fichiers"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📋 RÉSUMÉ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  ${GREEN}Succès  : $SUCCESS${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "  ${RED}Échecs  : $FAILED${NC}"
fi
echo ""

if [ $FAILED -eq 0 ]; then
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                                                            ║"
    echo "║     ✅ PROJET PRÊT POUR LE LANCEMENT ! ✅                 ║"
    echo "║                                                            ║"
    echo "║     Commande: python main.py                               ║"
    echo "║     Accès   : http://localhost:8000                        ║"
    echo "║                                                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
else
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                                                            ║"
    echo "║     ⚠️  PROBLÈMES DÉTECTÉS ⚠️                             ║"
    echo "║                                                            ║"
    echo "║     Veuillez corriger les erreurs ci-dessus               ║"
    echo "║                                                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
fi
