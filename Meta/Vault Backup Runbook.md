---
type: "runbook"
title: "Vault Backup — New Machine Setup"
tags: [meta, runbook, backup, git]
---

# 🖥️ Vault Backup — New Machine Setup Guide

> **Context**: The backup script commits and pushes the vault to a private GitHub repo.
> This is a **laptop**, so the backup uses a systemd timer with `Persistent=true` instead
> of a plain cron job. The difference: if the laptop was off or asleep when the timer
> was scheduled to fire, `Persistent=true` makes it run immediately on the next boot/wake
> rather than silently skipping.

---

## Prerequisites (one-time per machine)

### 1. Clone the vault from GitHub
```bash
git clone git@github.com:YOUR_USERNAME/obsidian-vault.git \
  "/home/$USER/Documents/Obsidian Vault"
```

Or if the folder already exists and you just need to link it:
```bash
cd "/home/$USER/Documents/Obsidian Vault"
git init
git remote add origin git@github.com:YOUR_USERNAME/obsidian-vault.git
git fetch origin
git checkout main
```

---

### 2. Set up SSH key for GitHub (if not already done)
```bash
# Generate a new SSH key (if you don't have one)
ssh-keygen -t ed25519 -C "vault-backup@$(hostname)"

# Print the public key — copy and add to GitHub:
# GitHub → Settings → SSH and GPG keys → New SSH key
cat ~/.ssh/id_ed25519.pub

# Test it works
ssh -T git@github.com
# Expected: "Hi YOUR_USERNAME! You've successfully authenticated..."
```

---

### 3. Make the backup script executable
```bash
chmod +x "/home/$USER/Documents/Obsidian Vault/Meta/vault-backup.sh"
```

---

## Option A — systemd Timer (Recommended for laptops ✅)

Unlike cron, a systemd timer with `Persistent=true` **catches up on missed runs**
after the laptop wakes from sleep or boots up. Use this on any machine that isn't
always on.

### Create the service unit
```bash
sudo tee /etc/systemd/system/vault-backup.service > /dev/null << 'EOF'
[Unit]
Description=Obsidian Vault Git Backup
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=zawiatgf
ExecStart=/bin/bash "/home/zawiatgf/Documents/Obsidian Vault/Meta/vault-backup.sh"
StandardOutput=append:/tmp/vault-backup.log
StandardError=append:/tmp/vault-backup.log
EOF
```

### Create the timer unit
```bash
sudo tee /etc/systemd/system/vault-backup.timer > /dev/null << 'EOF'
[Unit]
Description=Run Obsidian Vault Backup every 6 hours
Requires=vault-backup.service

[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
Persistent=true
RandomizedDelaySec=5min

[Install]
WantedBy=timers.target
EOF
```

> **`Persistent=true`** — if the timer fires while the laptop is off or asleep,
> it runs immediately the next time the machine is on.
>
> **`RandomizedDelaySec=5min`** — adds a random 0–5 min delay so all timers
> don't hammer the network at exactly 06:00:00.

### Enable and start
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vault-backup.timer

# Verify it's active
systemctl status vault-backup.timer
systemctl list-timers vault-backup.timer
```

### Check logs
```bash
# From systemd journal
journalctl -u vault-backup.service -f

# Or from the log file
tail -f /tmp/vault-backup.log
```

### Run immediately (manual trigger)
```bash
sudo systemctl start vault-backup.service
```

---

## Option B — cron job (Simpler, but misses runs while laptop is off)

Use this only if you prefer cron or the machine is always on.

```bash
crontab -e
```

Add this line:
```
# Obsidian vault auto-backup — every 6 hours
0 */6 * * * bash "/home/zawiatgf/Documents/Obsidian Vault/Meta/vault-backup.sh" >> /tmp/vault-backup.log 2>&1
```

To verify it was added:
```bash
crontab -l
```

---

## Verify the backup is working

```bash
# 1. Check git log in the vault
git -C "/home/zawiatgf/Documents/Obsidian Vault" log --oneline -5

# 2. Check the log file
cat /tmp/vault-backup.log

# 3. Run it manually right now
bash "/home/zawiatgf/Documents/Obsidian Vault/Meta/vault-backup.sh"
```

---

## Quick Reference

| Task | Command |
|---|---|
| Run backup now | `bash "/home/$USER/Documents/Obsidian Vault/Meta/vault-backup.sh"` |
| Check timer status | `systemctl status vault-backup.timer` |
| See next scheduled run | `systemctl list-timers vault-backup.timer` |
| View logs (live) | `tail -f /tmp/vault-backup.log` |
| Disable timer | `sudo systemctl disable --now vault-backup.timer` |
| Remove cron job | `crontab -e` → delete the line |

---

## Files involved

| File | Purpose |
|---|---|
| `Meta/vault-backup.sh` | The backup script (commit + push) |
| `/etc/systemd/system/vault-backup.service` | systemd service unit |
| `/etc/systemd/system/vault-backup.timer` | systemd timer (schedule) |
| `/tmp/vault-backup.log` | Runtime log (not tracked in git) |
