#!/bin/bash
#
# Backs up chroma_data/ (the vector database) to a timestamped zip file.
#
# IMPORTANT: the destination matters more than the script. A backup sitting
# in a subfolder of this same project, on the same disk, protects you against
# accidental deletion or a bad ingest run -- but NOT against your laptop's
# disk actually failing, since the original and the backup die together.
# For real protection, set BACKUP_DIR to a folder that's synced somewhere
# else automatically -- a Dropbox/Google Drive/iCloud Drive folder, for
# example -- so the sync itself gets a copy off this machine without you
# having to think about it again.
#
# Usage:
#   ./scripts/backup_chroma.sh
#   BACKUP_DIR=~/Dropbox/content-curator-backups ./scripts/backup_chroma.sh
#
# Rotation: keeps the last KEEP_LAST_N backups (default 14), deletes older
# ones automatically so this doesn't grow forever.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$PROJECT_DIR/chroma_data"
BACKUP_DIR="${BACKUP_DIR:-$HOME/content-curator-backups}"
KEEP_LAST_N="${KEEP_LAST_N:-14}"

if [ ! -d "$SOURCE_DIR" ]; then
  echo "No chroma_data directory found at $SOURCE_DIR -- nothing to back up yet."
  echo "(This is normal if you haven't ingested anything yet.)"
  exit 0
fi

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="$BACKUP_DIR/chroma_data_backup_$TIMESTAMP.zip"

cd "$PROJECT_DIR"
zip -rq "$BACKUP_FILE" chroma_data

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Backup created: $BACKUP_FILE ($BACKUP_SIZE)"

# Rotation: keep only the most recent KEEP_LAST_N backups, delete the rest.
cd "$BACKUP_DIR"
BACKUP_COUNT=$(ls -1 chroma_data_backup_*.zip 2>/dev/null | wc -l | tr -d ' ')
if [ "$BACKUP_COUNT" -gt "$KEEP_LAST_N" ]; then
  ls -1t chroma_data_backup_*.zip | tail -n +"$((KEEP_LAST_N + 1))" | while read -r old_backup; do
    echo "Removing old backup beyond retention limit: $old_backup"
    rm -- "$old_backup"
  done
fi

FINAL_COUNT=$(ls -1 chroma_data_backup_*.zip 2>/dev/null | wc -l | tr -d ' ')
echo "Backups retained: $FINAL_COUNT (keeping last $KEEP_LAST_N) in $BACKUP_DIR"

if [[ "$BACKUP_DIR" == "$PROJECT_DIR"* ]]; then
  echo
  echo "WARNING: your backup destination is inside this project's own folder,"
  echo "on the same disk as the original. This protects against accidental"
  echo "deletion but NOT against a disk failure. Consider setting BACKUP_DIR"
  echo "to a cloud-synced folder (Dropbox, Google Drive, iCloud Drive) instead."
fi
