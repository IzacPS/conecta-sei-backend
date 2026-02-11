#!/bin/bash
# PostgreSQL Backup Script for AutomaSEI
# Usage: ./scripts/backup-db.sh
# Cron example (daily at 3am): 0 3 * * * /path/to/scripts/backup-db.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
CONTAINER_NAME="${CONTAINER_NAME:-automasei_postgres}"
POSTGRES_DB="${POSTGRES_DB:-automasei}"
POSTGRES_USER="${POSTGRES_USER:-automasei}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/automasei_${TIMESTAMP}.sql.gz"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# Run pg_dump inside the container and compress
docker exec "$CONTAINER_NAME" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"

echo "[$(date)] Backup created: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# Cleanup old backups
DELETED=$(find "$BACKUP_DIR" -name "automasei_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "[$(date)] Deleted $DELETED old backup(s) (older than $RETENTION_DAYS days)"
fi

echo "[$(date)] Backup complete."
