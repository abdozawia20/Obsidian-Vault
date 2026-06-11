---
tags: [moc, personal, flutter, n8n, vercel]
---

# 🗺 Project MLT — Map of Content

> **Project MLT** — Personal life tracker app that aggregates tasks from Notion, Odoo, and ERPNext into a Flutter mobile app.

---

## 📄 Documents

| Document | Purpose |
|---|---|
| [[Architecture Plan - Unified Task Synchronization]] | Full system design: Vercel hub + n8n ETL + Flutter frontend |
| [[Local n8n Deployment & ngrok Routing Plan]] | Step-by-step guide to deploy n8n locally with ngrok tunnel |

---

## 🔗 Key Links Between Docs

- [[Local n8n Deployment & ngrok Routing Plan]] is a **prerequisite** for Phase 2 of → [[Architecture Plan - Unified Task Synchronization]]

---

## 🏗️ Architecture at a Glance

```
Notion ──┐
Odoo ────┤── n8n (ETL) ──► Vercel (Central Hub + Postgres) ──► Flutter App
ERPNext ─┘
```

---

## 🔗 Related

- [[../Home|🏠 Home]]
