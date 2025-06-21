# Quick Start Guide

Get Gmail to Podcast running in 10 minutes!

## 1. Prerequisites Check (1 minute)

```bash
# Check Python version (need 3.8+)
python --version

# Check pip
pip --version

# Check ffmpeg (for audio)
ffmpeg -version
```

## 2. Installation (3 minutes)

```bash
# Clone the repository
git clone https://github.com/yourusername/gmail-to-podcast.git
cd gmail-to-podcast

# Run automated setup
python setup.py
```

## 3. API Keys (3 minutes)

### Get OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Create new secret key
3. Copy the key

### Get Gemini API Key
1. Go to https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key

### Configure Keys
```bash
# Edit .env file
OPENAI_API_KEY=paste_your_openai_key_here
GEMINI_API_KEY=paste_your_gemini_key_here
```

## 4. Gmail Setup (2 minutes)

1. Download `credentials.json` from Google Cloud Console
   - See [docs/GMAIL_SETUP.md](docs/GMAIL_SETUP.md) if you need help
2. Place it in the project root

## 5. Your First Run (1 minute)

```bash
# Process last 7 days of emails
python src/run_full_pipeline.py --senders your@email.com --days-back 7

# Or use example senders
python src/run_full_pipeline.py --preset example_tech --days-back 7
```

## 🎉 That's it!

Your emails are now in the `output/` directory as markdown files.

## Next Steps

### Generate a Podcast
```bash
python src/run_full_pipeline.py --preset example_tech --days-back 7 --generate_podcast
```

### Configure Your Senders
Edit `config/senders/my_senders.json`:
```json
{
  "newsletters": {
    "description": "My newsletters",
    "senders": [
      "favorite@newsletter.com",
      "another@digest.org"
    ]
  }
}
```

Then use:
```bash
python src/run_full_pipeline.py --preset newsletters --days-back 7
```

### Common Commands

```bash
# Last week's emails with podcast
python src/run_full_pipeline.py --preset all --days-back 7 --generate_podcast

# Specific date range
python src/run_full_pipeline.py --preset newsletters --after 2025-01-01 --before 2025-01-31

# Skip filtering (get all emails)
python src/run_full_pipeline.py --preset all --days-back 3 --skip_llm_filter

# Custom output directory
python src/run_full_pipeline.py --preset tech --outdir my_digest --generate_podcast
```

## Troubleshooting

If something doesn't work:
1. Check [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
2. Run `python setup.py` again to verify setup
3. Make sure your API keys are correct in `.env`

## Tips

- Start with a small date range to test
- Use `--skip_llm_filter` to save API costs during testing
- Check `output/` directory for results
- Your personal config files are gitignored (safe to modify)