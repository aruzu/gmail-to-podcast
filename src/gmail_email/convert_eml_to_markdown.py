import argparse
from eml_to_markdown import convert_all_eml_to_markdown

def main():
    parser = argparse.ArgumentParser(description='Convert .eml files to Markdown.')
    parser.add_argument('--source', type=str, default='s2e2_sources/', help='Source directory for .eml files')
    parser.add_argument('--output', type=str, default='s2e2_markdown/', help='Output directory for .md files')
    args = parser.parse_args()
    convert_all_eml_to_markdown(args.source, args.output)

if __name__ == '__main__':
    main() 