#!/usr/bin/env python3
"""
Example usage of Gmail to Podcast

This script demonstrates various ways to use the tool.
"""

import subprocess
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))


def run_example(description, args):
    """Run an example command."""
    print(f"\n{'='*60}")
    print(f"Example: {description}")
    print(f"Command: python src/run_full_pipeline.py {' '.join(args)}")
    print('='*60)
    
    # Uncomment to actually run the commands
    # subprocess.run([sys.executable, "src/run_full_pipeline.py"] + args)
    print("(Command displayed - uncomment subprocess.run to execute)")


def main():
    """Show various usage examples."""
    print("Gmail to Podcast - Usage Examples")
    print("=================================")
    
    # Basic examples
    run_example(
        "Process last 7 days of emails from specific senders",
        ["--senders", "newsletter@example.com", "digest@example.org", "--days-back", "7"]
    )
    
    run_example(
        "Use a preset group of senders",
        ["--preset", "example_tech", "--days-back", "7"]
    )
    
    run_example(
        "Generate podcast from emails",
        ["--preset", "example_news", "--days-back", "7", "--generate_podcast"]
    )
    
    # Date range examples
    run_example(
        "Process specific date range",
        ["--preset", "all", "--after", "2025-01-15", "--before", "2025-01-22"]
    )
    
    run_example(
        "Flexible date formats",
        ["--preset", "newsletters", "--after", "20250115", "--before", "20250122"]
    )
    
    # Filtering examples
    run_example(
        "Skip LLM filtering (process all emails)",
        ["--preset", "all", "--days-back", "3", "--skip_llm_filter"]
    )
    
    run_example(
        "Custom filter description",
        ["--preset", "tech", "--days-back", "7", "--filter", "product announcements and updates only"]
    )
    
    run_example(
        "Filter including email body content",
        ["--preset", "all", "--days-back", "7", "--llm_filter_on_body"]
    )
    
    # Output directory examples
    run_example(
        "Custom output directory",
        ["--preset", "ai-news", "--days-back", "7", "--outdir", "weekly_ai_digest"]
    )
    
    run_example(
        "Separate directories for each step",
        ["--preset", "tech", "--days-back", "7", 
         "--eml_outdir", "emails/raw", 
         "--md_outdir", "emails/markdown"]
    )
    
    # Podcast options
    run_example(
        "Generate 45-minute podcast",
        ["--preset", "all", "--days-back", "7", "--generate_podcast", "--podcast_duration", "45"]
    )
    
    run_example(
        "Generate podcast from existing markdown",
        ["--preset", "any", "--skip_markdown", "--md_outdir", "existing_markdown/", "--generate_podcast"]
    )
    
    # Advanced usage
    run_example(
        "Full pipeline with all options",
        ["--preset", "newsletters",
         "--after", "2025-01-01",
         "--before", "2025-01-31",
         "--filter", "important updates and announcements",
         "--llm_filter_on_body",
         "--outdir", "january_digest",
         "--generate_podcast",
         "--podcast_duration", "30"]
    )
    
    print("\n" + "="*60)
    print("Configuration Tips:")
    print("="*60)
    print("1. Create your sender groups in: config/senders/my_senders.json")
    print("2. Customize settings in: config/config.yaml")
    print("3. Set API keys in: .env")
    print("4. Your personal files are gitignored and safe to modify")
    
    print("\n" + "="*60)
    print("For more information:")
    print("- Run: python src/run_full_pipeline.py --help")
    print("- Read: README.md")
    print("- Check: docs/TROUBLESHOOTING.md")


if __name__ == "__main__":
    main()