#!/usr/bin/env python3
"""
syncthing_watcher.py — Syncthing Event Watcher
================================================
Listens to the Syncthing REST event stream and triggers the vault
validator whenever the obsidian-vault folder changes.

Run as a systemd service on the server alongside Syncthing.

Requirements:
    pip install requests pyyaml

Environment variables:
    SYNCTHING_API_KEY   — from Syncthing Web UI → Actions → Settings → API Key
    SYNCTHING_URL       — default: http://127.0.0.1:8384
    SYNCTHING_FOLDER_ID — default: obsidian-vault

Deploy:
    cp Meta/syncthing_watcher.py /srv/vault-scripts/
    cp Meta/parse_vault.py /srv/vault-scripts/
    # Then enable the systemd service (see Meta/vault-watcher.service)
"""
import os
import sys
import time
import requests

# ── Configuration ─────────────────────────────────────────────────────────────
SYNCTHING_URL = os.environ.get("SYNCTHING_URL", "http://127.0.0.1:8384")
SYNCTHING_KEY = os.environ.get("SYNCTHING_API_KEY")
FOLDER_ID = os.environ.get("SYNCTHING_FOLDER_ID", "obsidian-vault")

if not SYNCTHING_KEY:
    print("ERROR: SYNCTHING_API_KEY environment variable not set.", file=sys.stderr)
    print("  Find it in Syncthing Web UI → Actions → Settings → API Key", file=sys.stderr)
    sys.exit(1)

# ── Import validator ──────────────────────────────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

try:
    from parse_vault import run_sync_validation
except ImportError:
    # Fallback: look in /srv/vault-scripts/
    sys.path.insert(0, "/srv/vault-scripts")
    from parse_vault import run_sync_validation


def watch_events():
    last_seen = 0
    headers = {"X-API-Key": SYNCTHING_KEY}
    print(f"🔍 Watching Syncthing events for folder '{FOLDER_ID}'...")
    print(f"   API: {SYNCTHING_URL}")

    while True:
        try:
            resp = requests.get(
                f"{SYNCTHING_URL}/rest/events",
                headers=headers,
                params={
                    "since": last_seen,
                    "events": "FolderScanProgress,LocalChangeDetected,FolderSummary",
                    "timeout": 60,
                },
                timeout=65,
            )
            resp.raise_for_status()
            events = resp.json()

            for event in events:
                last_seen = event["id"]
                folder = event.get("data", {}).get("folder", "")
                if folder == FOLDER_ID:
                    ts = event.get("time", "")[:19]
                    print(f"\n[{ts}] Change detected in '{FOLDER_ID}' — running validator...")
                    try:
                        data, errors = run_sync_validation()
                        print(f"   ✅ Parsed: {len(data)} projects | ⚠️  Errors: {len(errors)}")
                    except Exception as exc:
                        print(f"   ❌ Validator error: {exc}")

        except requests.exceptions.Timeout:
            pass  # Long-poll timeout is normal — loop continues immediately
        except requests.exceptions.ConnectionError as exc:
            print(f"⚠️  Syncthing connection error: {exc}. Retrying in 10s...")
            time.sleep(10)
        except Exception as exc:
            print(f"❌ Unexpected watcher error: {exc}. Retrying in 5s...")
            time.sleep(5)


if __name__ == "__main__":
    watch_events()
