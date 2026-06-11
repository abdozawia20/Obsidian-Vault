---
type: "project"
id: "proj_websers_versioning_analysis"
title: "Versioning Pipeline Analysis"
status: "active"
priority: "medium"
client: "Websers"
created_at: 2026-06-11T18:27:40+03:00
updated_at: 2026-06-11T18:27:40+03:00
tags:
  - project
---


# Expert Crew Analysis: Unified Versioning & Delivery Pipeline

> [!NOTE]
> This analysis is presented from the collective perspective of **CTO, Team Lead, Senior Developers, System Administrators, and DevOps Engineers**. Each section is attributed to the relevant role(s).

---

## Executive Verdict

| Aspect                     | Rating              | Notes                                                        |
| -------------------------- | ------------------- | ------------------------------------------------------------ |
| **Problem Identification** | ✅ Excellent         | The WhatsApp-APK problem is a real, measurable bottleneck    |
| **Versioning Schema**      | ✅ Solid             | Semantic + Odoo-native versioning is well-designed           |
| **Workflow Design**        | ⚠️ Good, with gaps  | Logical flow, but missing critical feedback loops            |
| **Automation Strategy**    | ⚠️ Needs refinement | Conceptually sound, but underspecifies key technical details |
| **Time Estimates**         | ⚠️ Optimistic       | iOS signing alone can consume Phase 1 entirely               |
| **Security Posture**       | 🔴 Incomplete       | Certificate/secret management needs a dedicated section      |
| **Scalability**            | ⚠️ Moderate         | Works for current team size, cracks will show at 10+ repos   |

**Overall**: **Approve with revisions.** The proposal correctly identifies the problem and proposes the right category of solution. However, it needs tactical refinements before execution to avoid a painful implementation that undermines team confidence in the new process.

---

## 1. Versioning Schema Review

### 🎯 CTO & Team Lead

#### Odoo Custom Modules — `[Odoo_Version].[Major].[Minor].[Patch]`

**Verdict: ✅ Correct approach.**

This follows Odoo's own convention and is required for module compatibility detection. No changes needed.

> [!TIP]
> Consider adding a pre-commit hook or CI check that validates the `__manifest__.py` version field was actually incremented before allowing a merge to `production`. Engineers **will** forget this — it's not a matter of if, but when.

#### Mobile Applications — `Major.Minor.Patch (Build Number)`

**Verdict: ✅ Good, but needs one clarification.**

The schema is clean and industry-standard. However:

> [!IMPORTANT]
> **The Build Number automation is not specified.** If engineers manually increment build numbers, you will get collisions and human error. The proposal should explicitly state:
> - Build numbers are **auto-incremented by the CI/CD pipeline**, not by developers.
> - The source of truth for the build number should be either:
>   - A counter stored in GitHub Actions (e.g., `github.run_number`)
>   - A value derived from git commit count
>   - A value managed via a small metadata file in the repo
>
> **Recommendation:** Use `github.run_number` as the build number. It's zero-maintenance and guaranteed unique per workflow.

#### 🔧 DevOps Addition: Version Bumping Strategy

The proposal says engineers "must update the version" but doesn't say **when** or **how** conflicts are handled:

| Scenario | What happens? |
|---|---|
| Two engineers both bump to `1.3.0` in parallel PRs | Merge conflict on version file — good, forces resolution |
| Engineer forgets to bump version | Silent regression — same version, different code |
| Hotfix needed on production while staging has unreleased work | Version collision between hotfix and next release |

**Recommendation:** Add a CI lint step that compares the version in the PR against the latest tag on the target branch. If not incremented → block the merge.

---

## 2. Workflow Analysis (Step-by-Step)

### Step 1: Project Planning & Task Initiation ✅

**👔 CTO/COO creates milestone in Odoo.**

No issues. This is organizational hygiene and correctly places ownership at the executive level.

> [!TIP]
> **Enhancement:** Create Odoo milestone templates so leadership doesn't start from a blank page every time. Include fields for: target version, target platforms (Android/iOS/both), expected PR count, and target delivery date.

---

### Step 2: Development & Staging Push ⚠️

**🧑‍💻 Engineers push to `main`, then PR to `staging`.**

> [!WARNING]
> **The branching model has a structural issue.** The proposal describes:
> ```
> feature branches → main → staging → production
> ```
> This is **non-standard** and creates confusion. In most Git workflows:
> - `main` (or `master`) **is** the production branch
> - `develop` is the integration branch
> - `staging` is a pre-production environment branch
>
> Having `main` sit **before** `staging` is counterintuitive and will confuse new hires and external contractors.

**Recommended branching model (pick one):**

````carousel
### Option A: GitFlow-Lite (Recommended for your team size)
```
feature/* → develop → staging → main (production)
                                  ↑
                              hotfix/*
```
- `develop`: Integration branch, where all features merge first
- `staging`: QA/testing branch, triggers staging builds
- `main`: Production branch, triggers release builds
- `hotfix/*`: Emergency fixes branched from `main`, merged back to both `main` and `develop`

**Pros:** Clean separation, well-documented pattern, tooling support
**Cons:** Slightly more branches to manage
<!-- slide -->
### Option B: Trunk-Based with Release Branches (Simpler)
```
main (trunk) → release/v1.2 → (tag v1.2.0)
     ↑
feature/*
```
- `main`: Single integration branch
- `release/vX.Y`: Cut when ready for QA, stabilized, then tagged
- No permanent `staging` branch — staging is just the latest `release/*` branch

**Pros:** Simpler, fewer long-lived branches
**Cons:** Less explicit staging step
````

---

### Step 3: Automated Staging Build & QA Handover ⚠️

**🤖 GitHub Actions builds APK/IPA → 🧑‍💻 Engineer posts link in Odoo Chatter.**

This step has **three issues**:

#### Issue 1: Manual link posting is a bottleneck

> [!IMPORTANT]
> The engineer manually copying artifact URLs to Odoo Chatter **reintroduces manual work** that this pipeline is supposed to eliminate. If the engineer is sick, on leave, or simply forgets — QA is blocked.
>
> **Fix:** Automate the Odoo notification. Odoo has a REST API. Add a step in the GitHub Action that:
> 1. Posts a message to the Odoo task's chatter via API call
> 2. Tags the relevant stakeholders
> 3. Includes the artifact download URL
>
> This is ~20 lines of YAML/shell in the workflow file.

#### Issue 2: GitHub Artifact expiration

The proposal correctly notes artifacts expire after 90 days. But:

- If QA takes 2 weeks and the client takes 3 months to approve, the staging artifact is **gone**
- There's no fallback for retrieving old staging builds

**Recommendation:** For staging builds, 90 days is fine. But consider publishing staging APKs to a **private distribution service** like:

| Service | Cost | Effort |
|---|---|---|
| Firebase App Distribution | Free (Google account) | Low — CLI integration |
| GitHub Releases (pre-release tag) | Free | Low — native |
| Self-hosted (Odoo attachment) | Free | Medium |

> [!TIP]
> **Firebase App Distribution** is the industry standard for this. It gives testers a dedicated app to download builds from, with version history and release notes. It's free and takes ~30 minutes to integrate into a GitHub Action.

#### Issue 3: iOS build compilation on GitHub Actions

> [!CAUTION]
> **Building iOS apps (`.ipa`) on GitHub Actions requires macOS runners.** GitHub's free tier includes **very limited** macOS minutes (reduced to a fraction of Linux minutes due to cost). For a company with multiple active apps:
>
> | Runner | Minutes/month (Free) | Cost after free tier |
> |---|---|---|
> | Linux | 2,000 | $0.008/min |
> | macOS | 200 | $0.08/min (10x Linux) |
>
> A single iOS build can consume 15-30 minutes. With staging + production builds across multiple apps, you could **exceed free limits within the first week.**
>
> **Mitigation options:**
> 1. Use a **self-hosted macOS runner** (a Mac Mini in the office)
> 2. Budget for GitHub Actions paid minutes
> 3. Use **Codemagic** or **Bitrise** for iOS builds (free tiers available)
> 4. Only build iOS on production merges, not staging (use TestFlight for iOS staging)

---

### Step 4: Code Review & Production Merge ✅

**👨‍💼 CTO reviews and merges to production.**

Sound process. One enhancement:

> [!TIP]
> Add **branch protection rules** to the production branch:
> - Require at least 1 approval (CTO or Lead Dev)
> - Require CI to pass before merge
> - Disable force-pushes and direct commits
> - Require linear history (no merge commits) — optional but cleaner

---

### Step 5: Automated Formal Release Generation ✅

**🤖 GitHub Actions builds, tags, and creates a Release.**

This is the strongest part of the proposal. GitHub's release automation is mature and reliable.

**DevOps note:** The workflow should:
```yaml
# Pseudocode for the release step
- Create a git tag (v1.2.0) from the merge commit
- Build APK and IPA in parallel jobs
- Create a GitHub Release with:
  - Auto-generated release notes (from PR titles)
  - APK attached as asset
  - IPA attached as asset
  - SHA256 checksums for verification
```

> [!TIP]
> Add **SHA256 checksums** to release assets. This allows anyone downloading the APK/IPA to verify file integrity — critical for client trust and security compliance.

---

### Step 6: Client Delivery ⚠️

**👔 CEO/COO downloads from GitHub and sends to client.**

> [!IMPORTANT]
> **This step still involves manual download-and-forward.** For internal efficiency, consider:
>
> 1. **For Play Store/App Store apps:** Automate submission to Google Play / App Store Connect via Fastlane. The CEO/COO then just approves the release in the store console.
> 2. **For direct APK delivery:** Generate a **clean, branded download page** (even a simple GitHub Pages site) instead of sending raw GitHub URLs to clients. Clients seeing `github.com/your-org/client-project/releases` exposes your internal tooling.
> 3. **For internal distribution:** Use Firebase App Distribution or a similar tool.

---

## 3. Changelog Generation Review ✅

**Verdict: Excellent — minimal overhead, maximum value.**

Using PR titles as changelog entries is the right call. Two refinements:

1. **Enforce PR title format with a CI check.** Use [Conventional Commits](https://www.conventionalcommits.org/) or a simpler house standard:
   - `feat: Add biometric login`
   - `fix: Crash on checkout screen`
   - `chore: Update dependencies`

   This allows the changelog to be **categorized** automatically (Features vs. Fixes vs. Maintenance).

2. **Link Odoo task IDs in PR descriptions.** Example: `Closes ODOO-1234`. This creates traceability from release notes → PR → Odoo task → original requirement.

---

## 4. Time Estimates Review

### 🔧 DevOps & System Admin Perspective

| Phase | Proposed | Realistic Estimate | Risk Factor |
|---|---|---|---|
| **Phase 1: Foundation** | 1–2 weeks | **2–4 weeks** | iOS signing, Fastlane setup, template testing across real projects |
| **Phase 2: Retrofit (per repo)** | 2–4 hours | **4–8 hours** | Branch restructuring + secrets + testing + fixing the inevitable build failures |
| **Phase 3: New Repos (per repo)** | 1–2 hours | **1–3 hours** | Reasonable if templates are solid |

> [!WARNING]
> **Phase 1 is significantly underestimated.** Here's why:
>
> | Sub-task | Estimated Time |
> |---|---|
> | Research & design workflow YAML | 4–8 hours |
> | Android build workflow (Gradle, signing) | 4–8 hours |
> | iOS build workflow (Xcode, provisioning) | 8–16 hours |
> | Fastlane Match setup for iOS certificates | 4–8 hours |
> | Release automation (tagging, notes, assets) | 4–6 hours |
> | Testing across a real project | 8–12 hours |
> | Documentation & team training | 4–8 hours |
> | **Total** | **36–66 hours (1–2 weeks full-time)** |
>
> The 1–2 week estimate is achievable **only if** the person doing it has prior GitHub Actions + Fastlane experience and dedicates full-time effort.

---

## 5. Missing Elements

### 🔴 Critical Gaps

| Gap | Impact | Recommendation |
|---|---|---|
| **No rollback procedure** | If a production release has a critical bug, there's no documented process to revert | Define: revert the merge commit, re-trigger CI, publish a patch release |
| **No hotfix workflow** | How do urgent fixes bypass the staging → production pipeline? | Add a `hotfix/*` branch pattern that goes directly to production (with CTO approval) |
| **No secret rotation policy** | Keystores and signing certificates have no expiration/rotation plan | Document annual rotation schedule, assign an owner |
| **No environment variable management** | Where do API keys, backend URLs, etc. live for different build flavors? | Use GitHub Environments (staging/production) with scoped secrets |
| **No monitoring/alerting for failed builds** | If a CI build fails, who gets notified? | Configure GitHub Action failure notifications → Slack/Email/Odoo |

### 🟡 Important Gaps

| Gap | Impact | Recommendation |
|---|---|---|
| **No team onboarding plan** | Developers used to WhatsApp workflow may resist | Plan a 1-hour workshop + written runbook |
| **No Flutter/React Native specifics** | Build commands differ wildly per framework | Templates must account for your actual tech stack |
| **No testing stage in CI** | The pipeline compiles but doesn't run tests | Add unit test + lint steps before compilation |
| **No app signing key backup** | If the engineer who created the keystore leaves, you lose the ability to update the app | Store keystore backups in a secure vault (not GitHub) |
| **No branch naming convention** | Engineers will use `fix`, `bugfix`, `hotfix`, `patch` interchangeably | Standardize: `feature/*`, `fix/*`, `hotfix/*`, `chore/*` |

---

## 6. Security Assessment

### 🛡️ System Admin & DevOps Perspective

| Concern | Current State | Recommendation |
|---|---|---|
| **Signing keys in GitHub Secrets** | Mentioned but not detailed | Use GitHub's encrypted secrets. **Never** commit keystores to the repo. Consider using a dedicated secrets manager (HashiCorp Vault) at scale |
| **iOS provisioning profiles** | Mentioned Fastlane Match | Fastlane Match stores certs in a private repo — ensure this repo has **strict access control** (CTO + 1 backup only) |
| **GitHub repo access** | Not mentioned | Enforce: branch protection, required reviews, no direct pushes to `staging`/`production` |
| **Artifact access** | GitHub artifacts are accessible to all repo collaborators | Acceptable for internal use. If repos are shared with clients, consider access scoping |
| **Odoo API credentials** | Needed for automated chatter posting | Store as GitHub Secret, use a dedicated Odoo service user (not a personal account) |

---

## 7. Recommendations Summary

### Immediate (Before Phase 1)

1. **Finalize the branching model** — resolve the `main` vs `staging` vs `production` hierarchy
2. **Choose your iOS build strategy** — GitHub macOS runners vs. self-hosted vs. Codemagic
3. **Audit your current tech stacks** — list every app framework (Flutter, React Native, Kotlin, Swift) to know what templates you need
4. **Set up a Firebase App Distribution account** — for staging build distribution

### During Phase 1

5. **Automate build number generation** — use `github.run_number`
6. **Automate Odoo chatter notifications** — don't leave manual link posting in the pipeline
7. **Add CI test steps** — lint + unit tests before compilation
8. **Write a developer runbook** — step-by-step "How to ship a feature" guide
9. **Set up branch protection rules** on all repos

### Post-Implementation

10. **Run a retrospective** after the first 3 releases through the new pipeline
11. **Track metrics**: time-from-PR-to-client-delivery, build failure rate, developer satisfaction
12. **Plan for App Store automation** — Fastlane deliver for Play Store / App Store Connect

---

## 8. Cost Analysis

| Item | Monthly Cost | Notes |
|---|---|---|
| GitHub Actions (Linux) | Free (2,000 min) | Sufficient for Android builds |
| GitHub Actions (macOS) | $0–$50+ | Depends on number of iOS builds |
| Firebase App Distribution | Free | Google account required |
| Self-hosted Mac Mini (one-time) | ~$700–$1,200 | Eliminates macOS runner costs |
| Fastlane (open source) | Free | Maintenance time is the real cost |
| **Developer time (Phase 1)** | **2–4 weeks of one engineer** | **This is the real cost** |

---

## Final Word

> [!IMPORTANT]
> This proposal is **strategically correct** — you absolutely need to move off the WhatsApp-APK model. The versioning schema is sound, the workflow is logical, and GitHub Actions is the right tool for a team your size.
>
> The gaps identified above are not reasons to reject the proposal — they're refinements that will make the difference between a pipeline that **works on paper** and one that **survives contact with reality**.
>
> **Recommended next step:** Address the critical gaps (branching model, iOS strategy, hotfix workflow, Odoo API automation), revise the time estimates, and then proceed with Phase 1 execution.
