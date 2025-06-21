#!/usr/bin/env python3
"""
Setup script for Gmail to Podcast

This script helps with initial setup, dependency installation, and configuration.
"""

import os
import sys
import subprocess
import shutil
import json
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.8 or higher."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required.")
        print(f"   You have Python {sys.version}")
        return False
    print(f"✅ Python {sys.version.split()[0]} detected")
    return True


def check_pip():
    """Check if pip is installed."""
    try:
        import pip
        print("✅ pip is installed")
        return True
    except ImportError:
        print("❌ pip is not installed")
        print("   Please install pip first")
        return False


def install_requirements(minimal=False):
    """Install Python requirements."""
    req_file = "requirements-minimal.txt" if minimal else "requirements.txt"
    print(f"\n📦 Installing Python dependencies from {req_file}...")
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
        print("✅ Python dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ Failed to install dependencies from {req_file}")
        if not minimal:
            print("   Trying minimal installation...")
            return install_requirements(minimal=True)
        return False


def check_ffmpeg():
    """Check if ffmpeg is installed."""
    if shutil.which("ffmpeg"):
        print("✅ ffmpeg is installed")
        return True
    else:
        print("⚠️  ffmpeg is not installed (required for audio/video processing)")
        print("   Install with:")
        print("   - macOS: brew install ffmpeg")
        print("   - Ubuntu: sudo apt-get install ffmpeg")
        print("   - Windows: Download from https://ffmpeg.org/download.html")
        return False


def setup_directories():
    """Create necessary directories."""
    dirs = [
        "config/senders",
        "output",
        "logs"
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    print("✅ Created directory structure")


def setup_config_files():
    """Set up configuration files."""
    # Copy default config if personal doesn't exist
    if not os.path.exists("config/config.yaml"):
        if os.path.exists("config/default_config.yaml"):
            shutil.copy("config/default_config.yaml", "config/config.yaml")
            print("✅ Created personal config file: config/config.yaml")
        else:
            print("⚠️  Default config not found")
    else:
        print("✅ Personal config already exists")
    
    # Create personal senders file if it doesn't exist
    personal_senders = "config/senders/my_senders.json"
    if not os.path.exists(personal_senders):
        print("\n📧 Setting up email senders...")
        create_sender_config(personal_senders)


def create_sender_config(filename):
    """Interactive sender configuration."""
    print("Let's set up your email senders.")
    print("You can add more later by editing: " + filename)
    
    senders = {}
    
    while True:
        print("\nAdd a sender group (or press Enter to finish):")
        group_name = input("Group name (e.g., 'newsletters'): ").strip()
        
        if not group_name:
            break
        
        description = input("Description: ").strip()
        
        print("Enter email addresses (one per line, empty line to finish):")
        emails = []
        while True:
            email = input("  Email: ").strip()
            if not email:
                break
            emails.append(email)
        
        if emails:
            senders[group_name] = {
                "description": description,
                "senders": emails
            }
    
    if senders:
        with open(filename, 'w') as f:
            json.dump(senders, f, indent=2)
        print(f"✅ Saved {len(senders)} sender groups to {filename}")
    else:
        # Create example file
        example_senders = {
            "example": {
                "description": "Example sender group",
                "senders": ["newsletter@example.com"]
            }
        }
        with open(filename, 'w') as f:
            json.dump(example_senders, f, indent=2)
        print(f"✅ Created example sender file: {filename}")


def setup_env_file():
    """Create .env file from template."""
    if os.path.exists(".env"):
        print("✅ .env file already exists")
        return True
    
    if os.path.exists(".env.example"):
        shutil.copy(".env.example", ".env")
        print("✅ Created .env file from template")
        print("   ⚠️  Please edit .env and add your API key:")
        print("      - GEMINI_API_KEY")
        return True
    else:
        print("❌ .env.example not found")
        return False


def check_gmail_credentials():
    """Check if Gmail credentials exist."""
    if os.path.exists("credentials.json"):
        print("✅ Gmail credentials.json found")
        return True
    else:
        print("⚠️  Gmail credentials.json not found")
        print("   Follow the Gmail API setup guide:")
        print("   1. Go to https://console.cloud.google.com/")
        print("   2. Create a project and enable Gmail API")
        print("   3. Create OAuth 2.0 credentials")
        print("   4. Download as credentials.json")
        print("   See docs/GMAIL_SETUP.md for details")
        return False


def check_api_keys():
    """Check if API keys are configured."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        gemini_key = os.getenv("GEMINI_API_KEY")
        
        keys_ok = True
        
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            print("✅ GEMINI_API_KEY is configured")
        else:
            print("⚠️  GEMINI_API_KEY not configured")
            print("   Get your key from: https://aistudio.google.com/app/apikey")
            keys_ok = False
        
        return keys_ok
    except ImportError:
        print("⚠️  Cannot check API keys (dotenv not installed yet)")
        return False


def main():
    """Run setup process."""
    print("Gmail to Podcast - Setup")
    print("========================\n")
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Check pip
    if not check_pip():
        sys.exit(1)
    
    # Create directories
    setup_directories()
    
    # Install requirements
    print("\nWould you like to install all dependencies or minimal only?")
    print("1. All (includes video generation)")
    print("2. Minimal (email and audio only)")
    choice = input("Choice (1/2): ").strip()
    
    minimal = choice == "2"
    if not install_requirements(minimal=minimal):
        print("\n⚠️  Setup completed with errors")
        sys.exit(1)
    
    # Check ffmpeg
    ffmpeg_ok = check_ffmpeg()
    
    # Setup config files
    setup_config_files()
    
    # Setup .env file
    env_ok = setup_env_file()
    
    # Check Gmail credentials
    gmail_ok = check_gmail_credentials()
    
    # Check API keys
    api_keys_ok = check_api_keys()
    
    # Summary
    print("\n" + "="*50)
    print("Setup Summary")
    print("="*50)
    
    all_good = ffmpeg_ok and env_ok and gmail_ok and api_keys_ok
    
    if all_good:
        print("✅ Setup completed successfully!")
        print("\n🚀 You're ready to start!")
        print("   Try: python src/run_full_pipeline.py --help")
    else:
        print("⚠️  Setup completed with warnings")
        print("\nNext steps:")
        
        if not gmail_ok:
            print("1. Set up Gmail API credentials")
        
        if not api_keys_ok:
            print("2. Add your API keys to .env")
        
        if not ffmpeg_ok:
            print("3. Install ffmpeg for audio processing")
        
        print("\nYou can still use the tool for email processing,")
        print("but some features may not work until setup is complete.")


if __name__ == "__main__":
    main()