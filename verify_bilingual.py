import asyncio
from unittest.mock import AsyncMock, patch
from services import LLMService
import json

async def test_bilingual_logic():
    print("Testing Bilingual Logic...")
    
    # Mock response from Ollama
    mock_response_content = json.dumps({
        "correction": "Привет, как дела?",
        "explanation": "Votre phrase était presque correcte, mais 'kak dela' est plus naturel.",
        "response": "У меня все хорошо, спасибо!"
    })
    
    # Mock the chat method to avoid network calls
    with patch.object(LLMService, 'chat', new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_response_content
        
        service = LLMService()
        
        # Test Case 1: User speaks Russian (target=ru)
        print("\nTest Case 1: Target=RU (User speaks RU, Native=FR)")
        result = await service.correct_and_respond("Privet kak dela", source_lang="ru", target_lang="ru")
        
        print(f"Result: {result}")
        
        assert result["correction"] == "Привет, как дела?"
        assert result["explanation"] == "Votre phrase était presque correcte, mais 'kak dela' est plus naturel."
        assert result["response"] == "У меня все хорошо, спасибо!"
        
        # Verify prompt structure
        
        # Verify prompt structure
        call_args = mock_chat.call_args[0][0]
        system_prompt = call_args[0]["content"]
        assert "parle Français" in system_prompt
        assert "apprend le Russe" in system_prompt
        
        print("Test Case 1 Passed!")

        # Test Case 2: Robust JSON Parsing (Markdown + Bad Escapes)
        print("\nTest Case 2: Robust JSON Parsing")
        # Mock response with Markdown and potential issues
        mock_chat.return_value = """
        Voici la réponse :
        ```json
        {
            "correction": "C'est bien.",
            "explanation": "Pas de problème.",
            "response": "Merci."
        }
        ```
        """
        result = await service.correct_and_respond("C'est bien", source_lang="fr", target_lang="ru")
        print(f"Result: {result}")
        assert result["correction"] == "C'est bien."
        assert result["explanation"] == "Pas de problème."
        
        print("Test Case 2 Passed!")

if __name__ == "__main__":
    asyncio.run(test_bilingual_logic())
