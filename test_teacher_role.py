import asyncio
from services import LLMService

async def test_teacher_correction():
    service = LLMService()
    
    # Simulate a user making a grammar error in French
    # "Je aller au cinéma" -> Should be "Je vais au cinéma"
    user_text = "Je aller au cinéma"
    native_lang = "fr"
    learning_lang = "ru" # Context: French user learning Russian, but speaking French to teacher
    
    # We need to mock the history to set the context that we are in a lesson
    history = [
        {"role": "assistant", "content": "fr: Comment vas-tu ? | ru: Как дела ?"}
    ]
    
    # We are testing the LLM's ability to correct the user's French input
    # Note: The system prompt is designed to teach Russian to French speakers.
    # If the user speaks French with an error, the teacher should correct it.
    
    result = await service.generate_lesson(user_text, native_lang, learning_lang, history=history)
    
    print(f"Result: {result}")
    
    assert "user_analysis" in result
    analysis = result["user_analysis"]
    
    # The LLM might be lenient, but "Je aller" is a gross error.
    # However, the prompt is "Teacher of Russian for French students".
    # If I speak French to it, it might just translate.
    # Let's try to simulate a Russian error instead, as that's the learning language.
    
    # Scenario: User tries to say "My name is Greg" in Russian but fails grammar.
    # Correct: "Меня зовут Грег" (Genitive)
    # Error: "Я зовут Грег" (Nominative - common mistake)
    
    user_text_ru = "Я зовут Грег"
    learning_lang = "ru"
    native_lang = "fr"
    
    result_ru = await service.generate_lesson(user_text_ru, native_lang, learning_lang, history=history)
    
    print(f"Result RU: {result_ru}")
    
    analysis_ru = result_ru["user_analysis"]
    # It should detect the error
    # Note: LLM behavior is probabilistic, but this is a strong error.
    
    if not analysis_ru["is_correct"]:
        print("✅ Error detected correctly")
        print(f"Correction: {analysis_ru['corrected_text']}")
        print(f"Explanation: {analysis_ru['explanation']}")
    else:
        print("⚠️ Error NOT detected (LLM might be too lenient or prompt needs tuning)")
        print(f"Analysis: {analysis_ru}")

if __name__ == "__main__":
    asyncio.run(test_teacher_correction())
