import asyncio
import sys
import os

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import LLMService

async def test_no_echo():
    print("🧪 Starting No-Echo Test")
    llm = LLMService()
    
    # User input that was echoed
    user_text = "Je pense aller faire les courses au supermarché."
    native_lang = "ru"
    learning_lang = "fr"
    level = "B1"
    
    print(f"Input: {user_text}")
    
    result = await llm.generate_lesson(user_text, native_lang, learning_lang, level=level)
    segments = result.get("segments", [])
    
    for seg in segments:
        if seg["lang"] == learning_lang:
            response_text = seg["text"]
            print(f"Response: {response_text}")
            
            # Check if response starts with the user text (fuzzy match or direct inclusion)
            # We want to avoid "Je pense que je vais aller faire les courses..." echoing "Je pense aller..."
            if "Je pense aller faire les courses" in response_text or "Je pense que je vais aller faire les courses" in response_text:
                 if len(response_text) < len(user_text) * 2: # heuristic: if response is mostly the echo
                     print("❌ FAILURE: AI echoed the user text.")
                     return

    print("✅ SUCCESS: AI did not echo the user text verbatim.")

if __name__ == "__main__":
    asyncio.run(test_no_echo())
