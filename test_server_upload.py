import httpx
import asyncio
import os

# Dummy WebM header (approximate) just to have non-zero content
# EBML + Segment + Info ...
DUMMY_WEBM = b'\x1A\x45\xDF\xA3\x9F\x42\x86\x81\x01\x42\xF7\x81\x01\x42\xF2\x81\x04\x42\xF3\x81\x08' + b'\x00' * 100

async def test_upload():
    print("creating test.webm...")
    with open("test.webm", "wb") as f:
        f.write(DUMMY_WEBM)
    
    file_size = os.path.getsize("test.webm")
    print(f"Test file size: {file_size} bytes")
    
    url = "http://localhost:8002/transcribe"
    print(f"Uploading to {url}...")
    
    async with httpx.AsyncClient() as client:
        try:
            with open("test.webm", "rb") as f:
                files = {'audio': ('test.webm', f, 'audio/webm')}
                response = await client.post(url, files=files, timeout=10.0)
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                print("✅ Upload successful (server accepted it)")
            else:
                print("❌ Upload failed (server rejected it)")
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            print("Is the server running on port 8002?")

if __name__ == "__main__":
    asyncio.run(test_upload())
