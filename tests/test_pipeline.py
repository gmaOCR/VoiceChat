import asyncio
import edge_tts
import httpx
import os
import json

# Configuration
API_URL = "http://mars.gregorymariani.com:8002"
TEST_TEXT = "Hello world, this is a test of the pronunciation analysis system."
TEST_LANG = "en"
OUTPUT_FILE = "test_audio.mp3"

async def generate_sample_audio():
    """Génère un fichier audio de test avec Edge TTS"""
    print(f"Generating audio for: '{TEST_TEXT}'...")
    communicate = edge_tts.Communicate(TEST_TEXT, "en-US-ChristopherNeural")
    await communicate.save(OUTPUT_FILE)
    print(f"Audio saved to {OUTPUT_FILE}")

async def test_analysis():
    if not os.path.exists(OUTPUT_FILE):
        await generate_sample_audio()
    
    print(f"Sending request to {API_URL}/analyze_pronunciation...")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            with open(OUTPUT_FILE, 'rb') as f:
                files = {'audio': (OUTPUT_FILE, f, 'audio/mpeg')}
                data = {
                    'text': TEST_TEXT,
                    'language': TEST_LANG
                }
                
                response = await client.post(
                    f"{API_URL}/analyze_pronunciation",
                    files=files,
                    data=data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print("\n✅ Analysis Successful!")
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                else:
                    print(f"\n❌ Error {response.status_code}: {response.text}")
                    
        except httpx.ConnectError:
            print(f"\n❌ Could not connect to {API_URL}. Is the server running?")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(test_analysis())
