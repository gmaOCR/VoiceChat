import asyncio
import sys
import os

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import LLMService

async def test_greeting():
    print("🧪 Starting Greeting Robustness Test")
    llm = LLMService()
    
    # Test cases: (native, learning, level)
    cases = [
        ("ru", "fr", "A1"),
        ("ru", "fr", "C1"),
        ("fr", "ru", "A1"),
        ("fr", "ru", "C1")
    ]
    
    for native_lang, learning_lang, level in cases:
        print(f"\n--- Testing {native_lang}->{learning_lang} Level {level} ---")
        try:
            result = await llm.generate_greeting(native_lang=native_lang, learning_lang=learning_lang, level=level)
            segments = result.get("segments", [])
            
            # Analyze output
            for seg in segments:
                lang = seg.get("lang")
                text = seg.get("text")
                print(f"[{lang}] {text}")
                
                # Check for "Da" issue
                if lang == native_lang and len(text.split()) < 3 and level == "C1":
                     print("❌ WARNING: Native translation seems too short!")

                if lang == native_lang and native_lang == "ru" and "Да" in text and len(text) < 10:
                     print("❌ DETECTED FAIL: 'Da' instead of translation.")

        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_greeting())
