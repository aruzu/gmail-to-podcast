# Troubleshooting Guide

Common issues and solutions for Gmail to Podcast.

## Installation Issues

### pip install fails with "error: Microsoft Visual C++ 14.0 is required"
**Platform**: Windows
**Solution**: 
- Install Visual Studio Build Tools from [Microsoft](https://visualstudio.microsoft.com/downloads/)
- Or use conda instead: `conda install -c conda-forge package_name`

### moviepy installation fails
**Solution**: 
- Try minimal installation: `pip install -r requirements-minimal.txt`
- Video generation is optional - the tool works without it

### "No module named 'audioop'" (Python 3.13+)
**Solution**:
```bash
pip install pyaudioop
# or
pip install audioop-compat
```

## Gmail API Issues

### "Access blocked: This app's request is invalid"
**Cause**: OAuth consent screen not configured properly
**Solution**:
1. Go to Google Cloud Console
2. Check OAuth consent screen configuration
3. Make sure your email is added as a test user
4. Ensure Gmail API is enabled

### "Token has been expired or revoked"
**Solution**:
```bash
rm token.pickle
# Run the tool again to re-authenticate
```

### "Quota exceeded for quota metric 'Queries'"
**Cause**: Hit Gmail API rate limits
**Solution**:
- Wait a few minutes and try again
- Process smaller batches of emails
- Use date ranges to limit the number of emails

### "HttpError 403: Insufficient Permission"
**Cause**: Wrong OAuth scope
**Solution**:
1. Delete `token.pickle`
2. Check that credentials.json has the correct scope
3. Re-authenticate

## Email Processing Issues

### No emails found
**Possible causes**:
1. Wrong date format - use YYYY/MM/DD or YYYYMMDD
2. No emails from specified senders in date range
3. Senders not configured correctly

**Debug steps**:
```bash
# Check your sender configuration
cat config/senders/my_senders.json

# Try with a wider date range
python src/run_full_pipeline.py --preset all --days-back 30
```

### LLM filtering removes all emails
**Solution**:
- Try different filter descriptions
- Use `--skip_llm_filter` to process all emails
- Enable body filtering: `--llm_filter_on_body`

## Podcast Generation Issues

### "Failed to generate podcast script"
**Possible causes**:
1. No markdown files found
2. OpenAI API key not set
3. API rate limits

**Solutions**:
- Check markdown directory has files
- Verify OPENAI_API_KEY in .env
- Wait and retry if rate limited

### Audio generation fails with "API key not valid"
**Solution**:
- Check GEMINI_API_KEY in .env
- Ensure key has TTS access enabled
- Try regenerating the API key

### No audio output or silent audio
**Possible causes**:
1. Script parsing failed
2. TTS API issues
3. Audio combining failed

**Debug steps**:
```bash
# Check if individual segments were created
ls output/*/audio_segments/

# Verify ffmpeg is installed
ffmpeg -version
```

### Video generation fails
**Solution**:
- Install moviepy: `pip install moviepy`
- Ensure ffmpeg is installed
- Try without video: remove `--generate_podcast` flag

## Configuration Issues

### "Preset not found"
**Solution**:
```bash
# List available presets
python src/run_full_pipeline.py --help

# Check your sender configuration
ls config/senders/
```

### Personal configuration not loading
**Ensure**:
1. Files are in correct location: `config/config.yaml`
2. YAML syntax is valid
3. No tabs in YAML files (use spaces)

## Performance Issues

### Processing is very slow
**Solutions**:
- Use date ranges to limit emails
- Enable `skip_existing` in config
- Process in smaller batches
- Increase delays between API calls

### High API costs
**Solutions**:
- Use `--skip_llm_filter` when possible
- Process only necessary emails
- Use shorter podcast durations
- Cache results to avoid reprocessing

## Common Error Messages

### "Please set the OPENAI_API_KEY environment variable"
```bash
# Check if .env file exists
ls -la .env

# Create from template
cp .env.example .env
# Edit .env and add your key
```

### "Error: Gmail credentials not found"
- Follow the [Gmail Setup Guide](GMAIL_SETUP.md)
- Ensure `credentials.json` is in project root

### "No emails found matching the criteria"
- Check sender email addresses are correct
- Verify date range contains emails
- Try `--skip_llm_filter` to see all emails

## Debug Mode

For more detailed output, set environment variables:
```bash
export DEBUG=1
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
```

## Getting Help

If you're still stuck:

1. Check the error message carefully
2. Look for similar issues on GitHub
3. Include in your bug report:
   - Python version
   - Operating system
   - Full error message
   - Steps to reproduce