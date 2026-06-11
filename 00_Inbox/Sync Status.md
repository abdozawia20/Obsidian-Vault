---
type: "system/sync-status"
tags:
  - system
---

# Sync Health Dashboard

## Parse Errors
> Last updated by server validator (`Meta/parse_vault.py`)

![[../.sync/errors.json]]

## Syncthing Status
> Check Syncthing Web UI: http://127.0.0.1:8384

- **Vault folder ID**: `obsidian-vault`
- **Versioning**: Simple — last 10 versions per file (`.stversions/`)
- **Watch for Changes**: Should be ON

## Conflict Files
```dataview
LIST
FROM ""
WHERE contains(file.name, "sync-conflict")
```

## Recent Notes Modified
```dataview
TABLE file.mtime as "Last Modified"
FROM ""
WHERE file.mtime >= date(today) - dur(1 day)
SORT file.mtime DESC
LIMIT 10
```
