#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# vault-backup.sh — Auto-commit and push the Obsidian vault to GitHub
#
# Usage (manual):   bash Meta/vault-backup.sh
# Usage (cron):     Managed via crontab — see Meta/vault-watcher.service or run:
#                   crontab -e
#
# Logs to:  /tmp/vault-backup.log  (last 500 lines kept)
# ──────────────────────────────────────────────────────────────────────────────

VAULT="/home/zawiatgf/Documents/Obsidian Vault"
LOG="/tmp/vault-backup.log"
MAX_LOG_LINES=500

# ── Logging helper ─────────────────────────────────────────────────────────────
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

# Trim log file to last N lines
trim_log() {
  if [ -f "$LOG" ]; then
    local lines
    lines=$(wc -l < "$LOG")
    if [ "$lines" -gt "$MAX_LOG_LINES" ]; then
      tail -n "$MAX_LOG_LINES" "$LOG" > "${LOG}.tmp" && mv "${LOG}.tmp" "$LOG"
    fi
  fi
}

# ── Main ───────────────────────────────────────────────────────────────────────
cd "$VAULT" || { log "ERROR: Vault directory not found at $VAULT"; exit 1; }

# Verify this is a git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  log "ERROR: Not a git repository. Run: git init"
  exit 1
fi

# Stage all changes
git add .

# Check if there is anything new to commit
if git diff --cached --quiet; then
  log "INFO: No changes — vault is already up to date."
  trim_log
  exit 0
fi

# Count changed files for the commit message
CHANGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

# Commit
if git commit -m "chore: vault snapshot ${TIMESTAMP} (${CHANGED} file(s) changed)"; then
  log "OK: Committed ${CHANGED} file(s)."
else
  log "ERROR: git commit failed."
  exit 1
fi

# Push (skip gracefully if no remote is configured)
REMOTE=$(git remote | head -1)
if [ -z "$REMOTE" ]; then
  log "WARN: No remote configured — commit saved locally only."
  log "      Add a remote with: git remote add origin <your-repo-url>"
  trim_log
  exit 0
fi

if git push "$REMOTE" main 2>&1 | tee -a "$LOG"; then
  log "OK: Pushed to $REMOTE/main."
else
  log "ERROR: Push failed. Will retry on next run."
  trim_log
  exit 1
fi

trim_log
