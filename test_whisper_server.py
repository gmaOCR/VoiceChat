#!/usr/bin/env python3
"""Test script to verify Whisper server on mars.gregorymariani.com"""
import httpx
import time

WHISPER_URL = "http://mars.gregorymariani.com:8001"

def test_health():
    """Test if server is online"""
    try:
        print(f"🔍 Testing {WHISPER_URL}/health...")
        start = time.time()
        response = httpx.get(f"{WHISPER_URL}/health", timeout=5.0)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            print(f"✅ Server online! Response time: {elapsed:.2f}s")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except httpx.ConnectError:
        print(f"❌ Cannot connect to {WHISPER_URL}")
        print("   Server may not be running or port 8001 not accessible")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_transcribe():
    """Test transcription endpoint with a small audio file"""
    try:
        print(f"\n🎤 Testing transcription endpoint...")
        # Would need an actual audio file to test
        print("   (Needs audio file to test - skipping)")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("WHISPER SERVER DIAGNOSTIC")
    print("=" * 60)
    
    health_ok = test_health()
    
    if health_ok:
        test_transcribe()
    else:
        print("\n📋 NEXT STEPS:")
        print("1. SSH to server: ssh greg@mars.gregorymariani.com")
        print("2. Navigate to project: cd /path/to/project")
        print("3. Install dependencies:")
        print("   pip install torch transformers accelerate fastapi uvicorn python-multipart")
        print("4. Run server: python whisper_server.py")
        print("5. Verify GPU: Check logs for 'cuda:0' or 'cpu'")
    
    print("=" * 60)
