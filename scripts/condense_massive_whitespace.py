#!/usr/bin/env python3
"""
condense_massive_whitespace.py: Remove lines of pure whitespace and collapse multiple blank lines.

Usage:
  condense_massive_whitespace.py INPUT_FILE [OUTPUT_FILE] [OPTIONS]

  INPUT_FILE:   Path to the input text file to process.
  OUTPUT_FILE:  (optional) Path where the processed text will be written. Defaults to INPUT_FILE (overwrite).

Options:
  -y, --yes    Overwrite output without confirmation when OUTPUT_FILE equals INPUT_FILE.
  -h, --help   Show this message and exit.

Features:
  - Reads entire file, normalizes CRLF to LF.
  - Splits on "\n" into lines.
  - Converts any line containing only whitespace into an empty line.
  - Rejoins lines with "\n".
  - Collapses any sequence of three or more consecutive newlines into exactly two newlines.

Requirements:
  pip install click
"""
import sys
import re
import click

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
    """Remove pure-whitespace lines and collapse excessive blank lines."""
    out_path = output_path or input_path

    # Confirm overwrite when needed
    if out_path == input_path and not yes:
        confirm = click.confirm(
            f"You are about to overwrite '{input_path}'. Continue?", default=False
        )
        if not confirm:
            click.echo('Aborted.')
            sys.exit(1)

    # Read and normalize line endings: CRLF -> LF
    with open(input_path, 'r', encoding='utf-8', errors='replace', newline='') as f:
        raw = f.read()
    text = raw.replace('\r\n', '\n').replace('\r', '')

    # Split into lines
    lines = text.split('\n')

    # Normalize pure-whitespace lines to empty
    processed_lines = []
    for line in lines:
        if line.strip() == '':
            processed_lines.append('')
        else:
            processed_lines.append(line)

    # Recombine text
    combined = '\n'.join(processed_lines)

    # Collapse three or more newlines into two
    collapsed = re.sub(r'\n{3,}', '\n\n', combined).strip()

    # Write result
    with open(out_path, 'w', encoding='utf-8', newline='\n') as out:
        out.write(collapsed)

if __name__ == '__main__':
    main()
