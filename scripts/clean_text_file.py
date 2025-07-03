#!/usr/bin/env python3
"""
clean_text_file.py: Normalize CRLF to LF and handle exotic whitespace characters with paragraphs and sections.

Usage:
  clean_text_file.py INPUT_FILE [OUTPUT_FILE] [OPTIONS]

  INPUT_FILE:  path to the input text file to clean.
  OUTPUT_FILE: (optional) path where the cleaned text will be written. Defaults to INPUT_FILE (overwrite).

Options:
  -y, --yes    Overwrite output file without prompting when OUTPUT_FILE equals INPUT_FILE.
  -h, --help   Show this message and exit.

Features:
  - Reads entire file into memory and normalizes CRLF to LF.
  - Removes stray CR (U+000D) not part of CRLF occurrences.
  - Handles form-feed (U+000C) that follows a newline by removing both the newline and the form-feed.
  - Splits into lines (dropping line endings), then processes with a manual progress bar.
  - Writes each cleaned line followed by a single LF, ensuring no extra whitespace.
  - Replaces paragraph separator (U+2029) with "\n" and section separator (U+2028) with "\n\n".
  - Removes other uncommon whitespace characters (vertical tab, no-break space, etc.).
  - Trims lines containing only whitespace characters to empty lines.

Requirements:
  pip install click tqdm
"""
import sys
import click
from tqdm import tqdm

# Unicode separators
PARAGRAPH_SEPARATOR = '\u2029'  # PARAGRAPH SEPARATOR
SECTION_SEPARATOR   = '\u2028'  # LINE SEPARATOR

# Other exotic whitespace to remove
EXOTIC_WHITESPACE = {
    '\u000C': 'FORM FEED',       # FF
    '\u000B': 'LINE TABULATION', # VT
    '\u00A0': 'NO-BREAK SPACE'   # NBSP
}

@click.command()
@click.argument(
    'input_path',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    required=True
)
@click.argument(
    'output_path',
    type=click.Path(writable=True, file_okay=True, dir_okay=False),
    required=False
)
@click.option(
    '-y', '--yes',
    is_flag=True,
    help='Overwrite output without confirmation when OUTPUT_FILE equals INPUT_FILE.'
)
def main(input_path, output_path, yes):
    """Normalize line endings, convert separators, and strip exotic whitespace with a progress bar."""
    out_path = output_path or input_path

    # Confirm overwrite when necessary
    if out_path == input_path and not yes:
        confirm = click.confirm(
            f"You are about to overwrite '{input_path}'. Continue?", default=False
        )
        if not confirm:
            click.echo('Aborted.')
            sys.exit(1)

    # Read file contents
    with open(input_path, 'r', encoding='utf-8', errors='replace', newline='') as f:
        raw = f.read()

    # Normalize line endings: CRLF -> LF, remove stray CR
    normalized = raw.replace('\r\n', '\n').replace('\r', '')

    # Handle form-feed preceded by newline: remove both the newline and the form-feed
    normalized = normalized.replace('\n' + '\u000C', '')

    # Split into lines (dropping line endings)
    lines = normalized.splitlines()
    total_lines = len(lines)

    with open(out_path, 'w', encoding='utf-8', newline='\n') as outfile:
        with tqdm(total=total_lines, desc="Cleaning", unit="line") as pbar:
            for line in lines:
                # Replace paragraph and section separators
                clean_line = (line
                              .replace(PARAGRAPH_SEPARATOR, '\n')
                              .replace(SECTION_SEPARATOR, '\n\n'))
                # Remove other exotic whitespace
                for ws in EXOTIC_WHITESPACE:
                    clean_line = clean_line.replace(ws, '')

                # Trim lines that contain only whitespace characters to empty lines
                if clean_line.strip() == '':
                    clean_line = ''

                # Write cleaned line with a single LF
                outfile.write(clean_line + '\n')
                pbar.update(1)

if __name__ == '__main__':
    main()
