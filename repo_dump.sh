#!/usr/bin/env bash

OUT="repo_dump.txt"

{
  echo "=== PROJECT FILE TREE ==="
  find . \( -name ".venv" -o -name "venv" -o -name ".git" -o -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" \) -prune \
    -o -type f ! -name "$OUT" -print | sort
  echo ""

  find . \( -name ".venv" -o -name "venv" -o -name ".git" -o -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" \) -prune \
    -o -type f \( -name "*.py" -o -name "*.md" -o -name "*.json" -o -name "*.csv" -o -name "*.txt" -o -name "*.sh" \) \
    ! -name "$OUT" -print | sort | while IFS= read -r f; do
      echo "=== FILE: $f ==="
      cat "$f"
      echo ""
    done
} > "$OUT"

echo "Done! Wrote $(wc -l < "$OUT") lines to $OUT"
