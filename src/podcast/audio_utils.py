"""
Audio utilities with Python 3.13 compatibility fixes.
Handles the missing audioop module in Python 3.13+.
"""

import sys

def check_audio_compatibility():
    """Check if audio processing modules are available"""
    try:
        from pydub import AudioSegment
        return True, "✅ Audio processing available"
    except ImportError as e:
        if "audioop" in str(e) or "pyaudioop" in str(e):
            return False, "❌ Missing audio module (Python 3.13+ compatibility issue)"
        else:
            return False, f"❌ Audio processing unavailable: {e}"

def install_audio_dependencies():
    """Install missing audio dependencies"""
    import subprocess
    
    print("🔧 Installing audio compatibility packages...")
    
    packages_to_try = [
        "pyaudioop",
        "audioop-compat", 
        "pydub[audio]"
    ]
    
    for package in packages_to_try:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ Installed {package}")
            
            # Test if this fixed the issue
            available, message = check_audio_compatibility()
            if available:
                print("✅ Audio processing now working")
                return True
                
        except subprocess.CalledProcessError:
            print(f"⚠️  Failed to install {package}")
            continue
    
    print("❌ Could not install audio dependencies")
    return False

def create_audio_fallback():
    """Create a basic audio processing fallback for when pydub fails"""
    
    class MockAudioSegment:
        """Fallback audio segment that creates empty files"""
        
        def __init__(self, data=None):
            self.data = data or b""
            
        def __add__(self, other):
            return MockAudioSegment()
            
        @classmethod
        def from_mp3(cls, file_path):
            return cls()
            
        @classmethod
        def silent(cls, duration=1000):
            return cls()
            
        def export(self, output_path, format="mp3", **kwargs):
            # Create an empty file
            with open(output_path, 'wb') as f:
                f.write(b"")
            print(f"⚠️  Created placeholder audio file: {output_path}")
    
    return MockAudioSegment

def get_audio_segment():
    """Get AudioSegment class, with fallback for compatibility issues"""
    try:
        from pydub import AudioSegment
        return AudioSegment
    except ImportError:
        print("⚠️  Using fallback audio processing (files will be empty)")
        return create_audio_fallback()