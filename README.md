# Gmail to Podcast

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
  [![Gemini API](https://img.shields.io/badge/Gemini-API-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
  ![Status: Experimental](https://img.shields.io/badge/Status-Experimental-orange.svg)

Transform your Gmail newsletters into engaging podcast episodes using AI. This tool fetches emails from specified senders, filters them intelligently, converts them to markdown, and generates natural-sounding podcast conversations.

> ⚠️ **Note**: The podcast generation feature is experimental and the quality may vary. This is a work in progress and improvements are ongoing.

## 🎯 Features

- **Smart Email Fetching**: Retrieve emails from specific senders with date filtering
- **AI-Powered Filtering**: Use Gemini to intelligently filter relevant emails
- **Markdown Conversion**: Convert emails to clean, readable markdown format
- **Podcast Generation**: Create engaging two-host podcast conversations using Gemini
- **Voice Synthesis**: Generate natural audio using Google's Gemini TTS
- **Video Creation**: Optional video generation with speaker indicators
- **Flexible Configuration**: Support for both personal and shared use cases
- **Preset Management**: Organize senders into reusable groups

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/gmail-to-podcast.git
cd gmail-to-podcast

# Run setup
python setup.py

# Configure your API keys
cp .env.example .env
# Edit .env with your API keys

# Run your first conversion
python src/run_full_pipeline.py --preset ai-news --days-back 7 --generate_podcast
```

## 📋 Prerequisites

- Python 3.8+
- Gmail account with API access enabled
- Google Gemini API key (for filtering, script generation, and voice synthesis)
- ffmpeg (for audio/video processing)

## 🔧 Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

For minimal installation (email processing only):
```bash
pip install -r requirements-minimal.txt
```

### 2. Set Up Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Gmail API
4. Create OAuth 2.0 credentials
5. Download as `credentials.json` and place in project root

See [docs/GMAIL_SETUP.md](docs/GMAIL_SETUP.md) for detailed instructions.

### 3. Configure API Keys

Create `.env` file with your API key:
```bash
GEMINI_API_KEY=your_gemini_key_here
```

### 4. Configure Senders

For personal use, create `config/senders/my_senders.json`:
```json
{
  "newsletters": {
    "description": "My favorite newsletters",
    "senders": [
      "newsletter@example.com",
      "digest@example.org"
    ]
  }
}
```

## 📚 Usage

### Basic Email to Podcast

```bash
# Process last 7 days of emails from a preset
python src/run_full_pipeline.py --preset newsletters --days-back 7 --generate_podcast

# Process specific date range
python src/run_full_pipeline.py --preset all --after 2025-01-01 --before 2025-01-31

# Use specific senders
python src/run_full_pipeline.py --senders news@site.com info@blog.org --days-back 3
```

### Advanced Options

```bash
# Skip LLM filtering (process all emails)
python src/run_full_pipeline.py --preset newsletters --days-back 7 --skip_llm_filter

# Custom output directory
python src/run_full_pipeline.py --preset newsletters --outdir weekly_digest --generate_podcast

# Filter with email body content (more thorough but slower)
python src/run_full_pipeline.py --preset newsletters --days-back 7 --llm_filter_on_body

# Custom podcast duration (5-60 minutes recommended)
python src/run_full_pipeline.py --preset newsletters --days-back 7 --generate_podcast --podcast_duration 15

# Mark processed emails as read and archive them
python src/run_full_pipeline.py --preset newsletters --days-back 7 --mark-processed
```

### Podcast Quality Tips

- **Duration**: 5-15 minutes work best for newsletter content
- **Content filtering**: Use specific, descriptive filters for better results
- **Email selection**: Process 3-7 days of content for optimal podcast length
- **Audio quality**: Ensure stable internet connection for TTS generation

### Working with Existing Files

```bash
# Generate podcast from existing markdown files
python src/run_full_pipeline.py --preset any --skip_markdown --md_outdir existing_markdown/ --generate_podcast

# Re-run with different filter
python src/run_full_pipeline.py --preset tech --days-back 7 --filter "only product announcements"
```

## 🔨 Configuration

### Configuration Hierarchy

The tool uses a flexible configuration system with this precedence:

1. Command line arguments (highest priority)
2. Environment variables
3. Personal config (`config/config.yaml`)
4. Default config (`config/default_config.yaml`)

### Personal Configuration

1. Copy the default config:
   ```bash
   cp config/default_config.yaml config/config.yaml
   ```

2. Create your sender presets:
   ```bash
   cp config/senders/example_senders.json config/senders/my_senders.json
   ```

3. Edit both files with your preferences

Your personal configuration files are gitignored and won't be shared.

### Available Presets

View available presets:
```bash
python src/run_full_pipeline.py --help
```

The `all` preset automatically includes all configured senders.

## 📁 Output Structure

```
output/
├── 20250121_20250128_eml/       # Raw email files
│   ├── message_id_1.eml
│   └── message_id_2.eml
├── 20250121_20250128_markdown/   # Converted markdown
│   ├── message_id_1.md
│   └── message_id_2.md
└── 20250121_20250128_podcast/    # Generated podcast
    ├── podcast_script.txt        # Conversation script
    ├── podcast.mp3              # Audio file
    └── podcast_video.mp4        # Video file (optional)
```

## 🎙️ Podcast Generation

The tool generates a natural conversation between two AI hosts:
- **Sarah**: Analytical, focused on insights and implications
- **Michael**: Enthusiastic, focused on practical applications

### Customization

Modify voices and styles in `config/config.yaml`:
```yaml
podcast:
  voices:
    sarah:
      name: "Kore"
      style: "analytical"
    michael:
      name: "Puck"
      style: "enthusiastic"
```

## 🧪 Testing

Run the test suite:
```bash
python -m pytest tests/

# Quick podcast test
python tests/minimal_podcast_test.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Gmail API for email access
- Google Gemini for intelligent filtering, script generation, and voice synthesis
- FFmpeg for audio/video processing

## 🐛 Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues and solutions.

## 🔒 Security Notes

- Never commit your API keys or `credentials.json`
- Use environment variables for sensitive data
- Review Gmail API permissions carefully
- Keep your `token.pickle` file secure

## 📧 Support

For issues and questions:
- Check [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- Open an issue on GitHub
- Review existing issues for solutions
