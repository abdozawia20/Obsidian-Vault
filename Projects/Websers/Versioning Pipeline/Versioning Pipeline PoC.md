---
type: "project"
id: "proj_websers_versioning_poc"
title: "Versioning Pipeline PoC"
status: "active"
priority: "medium"
client: "Websers"
created_at: 2026-06-11T18:27:40+03:00
updated_at: 2026-06-11T18:27:40+03:00
tags:
  - project
---


# Flutter Android Versioning Pipeline PoC

## Overview
This document outlines the Proof of Concept (PoC) for the automated versioning and delivery pipeline, specifically targeting a Flutter (Android-only) repository. It addresses the feedback from the initial proposal by incorporating automated build numbering, secure secret management, and a robust rollback strategy while maintaining the team's established branching model.

## 1. Branching Strategy
The pipeline will enforce the existing `main -> staging -> production` workflow.
- **`main` (Integration):** Feature branches (`feature/*`) are merged here for initial integration.
- **`staging` (QA):** `main` is merged into `staging` when ready for testing.
  - **Action:** Triggers the **Staging Build Workflow**.
- **`production` (Release):** `staging` is merged into `production` upon QA approval by the CTO/Lead.
  - **Action:** Triggers the **Release Workflow**.

## 2. Versioning & Build Numbers
- **Semantic Versioning:** The `pubspec.yaml` will dictate the `Major.Minor.Patch` version (e.g., `1.2.0`).
- **Automated Build Numbers:** To prevent Android collision errors, the pipeline will ignore the local build number and dynamically inject `github.run_number` during compilation using the `--build-number` flag.
  - *Example:* App version becomes `1.2.0 (104)` where `104` is the GitHub Action run number.

## 3. Environment Variable Management
To ensure security and prevent unauthorized access:
- **GitHub Secrets:** All sensitive variables (API keys, backend URLs) will be stored in GitHub Secrets.
- **Injection:** Variables will be injected at build time using Flutter's `--dart-define` (or equivalent), eliminating the need to commit `.env` files to the repository.
- **Environments:** GitHub Environments will be utilized to separate `staging` and `production` secrets, adding an extra layer of access control.

## 4. Workflows & Automation
### A. Staging Build Workflow
- **Trigger:** Push/Merge to `staging`.
- **Process:**
  1. Compiles the Android APK using staging environment secrets.
  2. Uploads the generated APK as a temporary GitHub Artifact (expires in 90 days).
- **Handover:** The engineer copies the Artifact URL and manually pastes it into the Odoo task chatter for QA testing. (Native GitHub Action notifications via email/mobile app will alert developers of build status).

### B. Production Release Workflow
- **Trigger:** Push/Merge to `production`.
- **Process:**
  1. Compiles the Android APK using production environment secrets.
  2. Generates a formal GitHub Release.
  3. Applies the version tag automatically.
  4. Automatically compiles a changelog from PR titles merged since the last release.
  5. Attaches the compiled APK permanently to the GitHub Release.

### C. Rollback Workflow
- **Trigger:** Manual dispatch via GitHub UI.
- **Process:**
  1. User inputs a specific previous tag (e.g., `v1.1.0`).
  2. The workflow checks out the code at that specific tag.
  3. Re-compiles the app with a fresh, incremented build number to allow installation.
  4. Publishes a new "Rollback" release.
  - *Note:* This strategy supports both compiled apps (Flutter) and source-based code (Odoo modules) by relying on git history rather than pre-compiled binaries.

## 5. Security & Protections
- **Branch Protection:**
  - `staging`: Requires pull request reviews before merging.
  - `production`: Requires CTO/Lead approval and successful CI checks before merging. Direct pushes are disabled.
