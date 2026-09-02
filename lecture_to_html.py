#!/usr/bin/env python3
"""
lecture_to_html.py

Convert a plain-text lecture-notes file into a styled HTML file, using the
same prompt / note / argument / quote structure as your lecture-notes.css
template. Drop the output next to styles.css in your GitHub Pages repo.

MARKUP FORMAT
=============
# Lecture Title                   <- first line, becomes <h1>
## Subtitle                       <- optional second line, becomes .subtitle

The rest of the file is a series of blocks. Each block starts with a tag
on its own line (case-insensitive, colon optional):

    prompt:
    note:              (alias: "instructor note:")
    argument:
    quote:

Everything after a tag line belongs to that block, until the next tag line
or the end of the file.

  - Inside prompt / note / quote blocks, a blank line starts a new
    paragraph.
  - Inside argument blocks, line breaks are preserved exactly as typed
    (so your "(1) ... (2) ... So: (3) ..." lists keep their line breaks).
  - Wrapping a word or phrase in *asterisks* renders it as <em>italics</em>.
  - Straight quotes (" and ') are automatically converted to curly quotes.

NESTING an argument, quote, or table INSIDE a prompt or note:
  Indent the "argument:", "quote:", or "table:" tag line (a few spaces or
  a tab) and it will be nested inside the prompt/note above it instead of
  becoming its own separate block. An unindented tag always starts a new
  top-level block. "prompt:" and "note:" themselves are always top-level
  and cannot be nested.

  To go back to writing plain prompt/note text after a nested sub-block,
  just dedent your next line back to the left margin -- no closing tag
  needed. The sub-block ends automatically as soon as it sees a non-blank
  line that isn't indented.

Any line starting with % anywhere in the file is treated as a comment and
dropped entirely -- handy for keeping cut material in your notes file
without it ending up in the HTML.

EXAMPLE INPUT
=============
# Anselm's Ontological Argument
## Philosophy -- Lecture notes

prompt:
Here we have this argument from Anselm. It's meant to show that God
exists.

note:
Select student at random.

prompt:
Might there be multiple things than which nothing greater can be thought?

    argument:
    (1) God is the greatest thing that can be thought of

quote:
"Something than which nothing greater can be thought."

% this whole line is a comment and will be dropped

USAGE
=====
    python lecture_to_html.py input.txt output.html
"""

import sys
import re
import html
import textwrap
from pathlib import Path

TAG_PATTERN = re.compile(
    r'^(prompt|note|instructor note|argument|quote|table)\s*:?\s*$',
    re.IGNORECASE,
)

NESTABLE_TAG_PATTERN = re.compile(
    r'^(argument|quote|table)\s*:?\s*$',
    re.IGNORECASE,
)

TAG_MAP = {
    'prompt': 'prompt',
    'note': 'note',
    'instructor note': 'note',
    'argument': 'argument',
    'quote': 'quote',
    'table': 'table',
}


def smart_quotes(text):
    """Convert straight double quotes to curly open/close quotes, and
    straight apostrophes to a typographic apostrophe/closing single quote."""
    result = []
    open_double = True
    for ch in text:
        if ch == '"':
            result.append('\u201c' if open_double else '\u201d')
            open_double = not open_double
        elif ch == "'":
            result.append('\u2019')
        else:
            result.append(ch)
    return ''.join(result)


def format_inline(text):
    """Escape HTML-sensitive characters, apply *emphasis*, then smart quotes."""
    text = html.escape(text, quote=False)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = smart_quotes(text)
    return text


def paragraphs_html(raw_lines, indent='    '):
    """Join raw lines into <p> paragraphs, splitting on blank lines."""
    paragraphs = []
    current = []
    for line in raw_lines:
        if line.strip() == '':
            if current:
                paragraphs.append(' '.join(current))
                current = []
        else:
            current.append(line.strip())
    if current:
        paragraphs.append(' '.join(current))
    return '\n'.join(f'{indent}<p>{format_inline(p)}</p>' for p in paragraphs)


def argument_text(raw_lines):
    """Preserve line breaks for argument blocks; trim leading/trailing
    blanks, and dedent so indentation used only to signal nesting inside
    a prompt/note doesn't become part of the visible content."""
    lines = list(raw_lines)
    while lines and lines[0].strip() == '':
        lines.pop(0)
    while lines and lines[-1].strip() == '':
        lines.pop()
    dedented = textwrap.dedent('\n'.join(lines)).split('\n')
    return '\n'.join(html.escape(line, quote=False) for line in dedented)


def table_html(raw_lines):
    """Render a pipe-delimited table. First non-blank row is the header
    (its first cell is usually left blank -- the corner cell). Each
    subsequent row's first cell becomes a row header (<th>); the rest
    become data cells (<td>)."""
    rows = []
    for line in raw_lines:
        if line.strip() == '':
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)

    if not rows:
        return '  <table class="matrix"></table>'

    header, body = rows[0], rows[1:]
    thead_html = ''.join(f'<th>{format_inline(c)}</th>' for c in header)

    body_rows = []
    for row in body:
        if not row:
            continue
        row_header, rest = row[0], row[1:]
        cells = f'<th scope="row">{format_inline(row_header)}</th>'
        cells += ''.join(f'<td>{format_inline(c)}</td>' for c in rest)
        body_rows.append(f'      <tr>{cells}</tr>')
    tbody_html = '\n'.join(body_rows)

    return (
        '  <table class="matrix">\n'
        f'    <thead><tr>{thead_html}</tr></thead>\n'
        '    <tbody>\n'
        f'{tbody_html}\n'
        '    </tbody>\n'
        '  </table>'
    )


def parse_top_level(lines):
    """Split the file into top-level blocks. A tag line only starts a new
    top-level block if it is NOT indented; indented argument/quote/table
    tag lines are left inside the current block's raw lines, to be picked
    up later by split_segments() as nested content."""
    blocks = []
    current_tag = None
    current_lines = []

    def flush():
        if current_tag is not None:
            blocks.append((current_tag, current_lines[:]))

    for line in lines:
        stripped = line.strip()
        is_indented = bool(line) and line[0].isspace()
        m = TAG_PATTERN.match(stripped) if stripped else None
        if m and not is_indented:
            flush()
            current_tag = TAG_MAP[m.group(1).lower()]
            current_lines = []
        else:
            current_lines.append(line)
    flush()
    return blocks


def split_segments(raw_lines):
    """Within a prompt/note block's raw lines, split into an ordered list
    of ('text', lines) and ('argument'/'quote'/'table', lines) segments,
    based on indented sub-tag lines.

    A nested sub-block runs for as long as its lines stay indented. The
    first non-blank line that dedents back to the left margin ends the
    sub-block and resumes plain prompt/note text -- no closing tag
    needed. Blank lines inside a sub-block don't end it by themselves;
    only the indentation of the next real line decides."""
    segments = []
    current_type = 'text'
    current_lines = []
    pending_blanks = []

    def flush():
        segments.append((current_type, current_lines[:]))

    for line in raw_lines:
        stripped = line.strip()

        if stripped == '':
            pending_blanks.append(line)
            continue

        is_indented = line[0].isspace()

        if current_type != 'text' and not is_indented:
            # Dedented back to the margin: end the sub-block (dropping the
            # blank line(s) that separated it) and resume plain text.
            flush()
            current_type = 'text'
            current_lines = []
            pending_blanks = []

        if pending_blanks:
            current_lines.extend(pending_blanks)
            pending_blanks = []

        m = NESTABLE_TAG_PATTERN.match(stripped) if is_indented else None
        if m:
            flush()
            current_type = m.group(1).lower()
            current_lines = []
        else:
            current_lines.append(line)

    flush()
    return segments


def render_segments(raw_lines, base_indent='    '):
    """Render a prompt/note body that may contain nested argument/quote/
    table sub-blocks, in the order they appeared."""
    parts = []
    for seg_type, seg_lines in split_segments(raw_lines):
        if seg_type == 'text':
            part = paragraphs_html(seg_lines, indent=base_indent)
        elif seg_type == 'argument':
            part = f'{base_indent}<div class="argument">{argument_text(seg_lines)}</div>'
        elif seg_type == 'quote':
            inner = paragraphs_html(seg_lines, indent=base_indent + '  ')
            part = f'{base_indent}<div class="blockquote">\n{inner}\n{base_indent}</div>'
        elif seg_type == 'table':
            part = table_html(seg_lines)
        else:
            part = ''
        if part.strip():
            parts.append(part)
    return '\n\n'.join(parts)


def block_to_html(tag, raw_lines):
    if tag == 'prompt':
        inner = render_segments(raw_lines)
        return f'  <div class="prompt">\n{inner}\n  </div>'
    if tag == 'note':
        inner = render_segments(raw_lines)
        return f'  <div class="note">\n{inner}\n  </div>'
    if tag == 'argument':
        inner = argument_text(raw_lines)
        return f'  <div class="argument">{inner}</div>'
    if tag == 'quote':
        inner = paragraphs_html(raw_lines, indent='      ')
        return f'  <div class="blockquote">\n{inner}\n  </div>'
    if tag == 'table':
        return table_html(raw_lines)
    raise ValueError(f'Unknown tag: {tag}')


def convert(input_text):
    lines = input_text.splitlines()
    lines = [l for l in lines if not l.lstrip().startswith('%')]

    title = 'Untitled Lecture'
    subtitle = ''
    idx = 0

    while idx < len(lines) and lines[idx].strip() == '':
        idx += 1

    if idx < len(lines) and lines[idx].strip().startswith('#'):
        title = lines[idx].lstrip('#').strip()
        idx += 1
        while idx < len(lines) and lines[idx].strip() == '':
            idx += 1
        if idx < len(lines) and lines[idx].strip().startswith('##'):
            subtitle = lines[idx].lstrip('#').strip()
            idx += 1

    body_lines = lines[idx:]
    blocks = parse_top_level(body_lines)
    body_html = '\n\n'.join(block_to_html(tag, raw) for tag, raw in blocks)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(title, quote=False)} \u2014 Lecture Notes</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<main>

  <h1>{format_inline(title)}</h1>
  <p class="subtitle">{format_inline(subtitle)}</p>

{body_html}

</main>
<script src="script.js"></script>
</body>
</html>
'''


def main():
    if len(sys.argv) != 3:
        print('Usage: python lecture_to_html.py input.txt output.html')
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    text = input_path.read_text(encoding='utf-8')
    output_path.write_text(convert(text), encoding='utf-8')
    print(f'Wrote {output_path}')


if __name__ == '__main__':
    main()
