#!/bin/bash
#
# Restores chroma_data/ from a backup zip created by backup_chroma.sh.
#
# Safety behavior: if a chroma_data/ directory already exists, it is moved
# aside (not deleted) before restoring, so a bad restore is itself
# recoverable. You'll see where it went in the output.
#
# Usage:
#   ./scripts/restore_chroma.sh ~/content-curator-backups/chroma_data_backup_2026-07-04_10-30-00.zip

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$PROJECT_DIR/chroma_data"

if [ $# -ne 1 ]; then
  echo "Usage: $0 path/to/chroma_data_backup_TIMESTAMP.zip"
  echo
  echo "Available backups in the default backup location:"
  ls -1t "$HOME/content-curator-backups"/chroma_data_backup_*.zip 2>/dev/null || echo "  (none found at default location -- check your BACKUP_DIR if you used a custom one)"
  exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

if [ -d "$SOURCE_DIR" ]; then
  SAFETY_COPY="$PROJECT_DIR/chroma_data_before_restore_$(date +%Y-%m-%d_%H-%M-%S)"
  echo "Existing chroma_data/ found -- moving it to:"
  echo "  $SAFETY_COPY"
  echo "instead of deleting it, in case this restore isn't what you wanted."
  mv "$SOURCE_DIR" "$SAFETY_COPY"
fi

echo "Restoring from: $BACKUP_FILE"
cd "$PROJECT_DIR"
unzip -q "$BACKUP_FILE"
echo "Restore complete. chroma_data/ now reflects the backup."
echo
echo "Once you've confirmed the server works correctly with this data,"
echo "you can delete the safety copy manually if one was created above."
