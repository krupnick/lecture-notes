#!/bin/bash
#
# watch.sh — automatically re-run lecture_to_html.py whenever a .txt file
# in this folder is created or changed, so you don't have to type the
# conversion command by hand each time.
#
# SETUP
#   Keep this file in the same folder as lecture_to_html.py and your
#   .txt / .html lecture files.
#
#   Make it runnable (only needs to be done once, ever):
#     chmod +x watch.sh
#
# USAGE
#   Open Terminal, cd into the folder, then run:
#     ./watch.sh
#
#   Leave that Terminal window open while you work. Every time you save
#   changes to a .txt file, it'll notice within a couple seconds and
#   regenerate the matching .html file automatically. Press Ctrl+C in
#   that window to stop watching.
#
# NOTE
#   This checks the folder every 2 seconds rather than reacting the
#   instant you save (called "polling") — simple and needs no extra
#   software. If you want truly instant conversion, you can install a
#   tool called fswatch (`brew install fswatch`) and use it instead;
#   ask me if you want that version.

FOLDER="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$FOLDER/lecture_to_html.py"

if [ ! -f "$SCRIPT" ]; then
  echo "Error: lecture_to_html.py not found in $FOLDER"
  echo "Make sure watch.sh is in the same folder as lecture_to_html.py."
  exit 1
fi

echo "Watching $FOLDER for changed .txt files... (Ctrl+C to stop)"

while true; do
  for txt in "$FOLDER"/*.txt; do
    [ -e "$txt" ] || continue
    base="$(basename "$txt" .txt)"
    html="$FOLDER/$base.html"

    if [ ! -e "$html" ] || [ "$txt" -nt "$html" ]; then
      echo "Converting $base.txt -> $base.html"
      python3 "$SCRIPT" "$txt" "$html"
    fi
  done
  sleep 2
done
