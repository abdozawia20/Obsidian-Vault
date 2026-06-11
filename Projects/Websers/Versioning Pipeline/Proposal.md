---
type: "project"
id: "proj_websers_versioning_proposal"
title: "Versioning Pipeline Proposal"
status: "active"
priority: "medium"
client: "Websers"
created_at: 2026-06-11T18:27:40+03:00
updated_at: 2026-06-11T18:27:40+03:00
tags:
  - project
---


This note is a direct continuation from [[Versioning Pipeline Analysis (From Farhat)]]

**Objective:** To establish a standardized versioning schema and an automated, zero-customization delivery pipeline leveraging out-of-the-box (OOTB) features of GitHub and our internal Odoo instance. This process ensures executive oversight, automates manual compilation, and maintains developer momentum.

**Coverage and requirements:** This pipeline requires the use of the internal Odoo instance to track task/feature progress, GitHub for tracking versioning, and an optional Keystores/Certificates for faster android/apple app store publishing.

# 1. Versioning Schema

To maintain consistency and compatibility, we will enforce strict versioning rules across our two distinct project types.

### Odoo Custom Modules

Odoo requires a specific versioning structure to map module compatibility to the core Odoo platform.

- **Schema:** [Odoo_Version].[Major].[Minor].[Patch]
    
- **Format Example:** 18.0.1.2.0 (indicates Odoo 18 compatibility, module version 1.2.0).
    
- **Implementation:** Engineers must update the version key within the module's __manifest__.py file prior to merging code into the production branch.
    

### Custom Mobile Applications

Mobile apps have independent lifecycles and will follow standard Semantic Versioning, coupled with build numbers for internal and device tracking.

- **Schema:** Major.Minor.Patch (Build Number)
    
- **Format Example:** Version 2.1.0 (Build 104).
    
- **Implementation:** * **Major:** Significant new features or UI overhauls.
    
    - **Minor:** New functionality that is backwards compatible.
        
    - **Patch:** Bug fixes.
        
    - **Build Number:** An internal, incrementally increasing integer required by iOS/Android systems to differentiate between compiled files of the exact same version.
        

# 2. Chronological Release Workflow

By utilizing GitHub Actions and strict Git branching (staging and production), we remove the manual burden of compiling .apk and .ipa files. The following represents the step-by-step lifecycle of a project update.

### Step 1: Project Planning & Task Initiation

- **Who:** CEO / COO
    
- **Where:** Internal Odoo Instance
    
- **Action:** Leadership creates a milestone or task in Odoo's Project module (e.g., "Develop For Client X Mobile App v1.2") to track the upcoming release.
    

### Step 2: Development & Staging Push

- **Who:** Software Engineers
    
- **Where:** GitHub
    
- **Action:** Engineers write the code locally. Once ready for testing, they open a Pull Request (PR) to merge their feature branches into the main branch. Once all of the requested feature have been implemented, they open another Pull Request (PR) to merge everything into the staging branch.
    

### Step 3: Automated Staging Build & QA Handover

- **Who:** GitHub Actions (Automation) -> Engineers
    
- **Where:** GitHub -> Odoo Chatter
    
- **Action 1**: Merging into staging automatically triggers GitHub
    
- **Actions 2**: The pipeline compiles the code and attaches the resulting APK/IPA as temporary **Artifacts** directly to the GitHub workflow run.
    
- **Action 3**: The Engineer copies the URL of this Artifact and pastes it into the Odoo Task's Chatter (@COO, Staging build for v1.2 is ready for review: [Link]) Artifacts are deleted after 90 days of their generation by default in GitHub.
    

### Step 4: Code Review & Production Merge

- **Who:** CTO / Lead Developer
    
- **Where:** GitHub
    
- **Action:** Once staging is approved by QA/Leadership, the CTO reviews the codebase for quality. If approved, the CTO executes the merge from staging into the production branch.
    

### Step 5: Automated Formal Release Generation

- **Who:** GitHub Actions (Automation)
    
- **Where:** GitHub
    
- **Action:** 1. Merging into production triggers the final CI/CD pipeline.
    
- **Action 2**: The automation compiles the production-ready APK/IPA.
    
- **Action 3**: The automation automatically drafts a formal **GitHub Release** page, applies the version tag (e.g., v1.2.0), and permanently uploads the compiled apps as release assets.
    

### Step 6: Client Delivery

- **Who:** CEO / COO
    
- **Where:** Odoo / Email
    
- **Action:** Leadership receives the final GitHub Release link (via Odoo Chatter notification), downloads the finalized .apk or .ipa files, and forwards them directly to the client.
    

# 3. Automated Changelog Generation

Because the final release generation is entirely handled by automation, manually typing out changelogs creates a bottleneck. Instead, we will rely on GitHub Actions' native ability to compile changelogs dynamically.

- **The Standard:** Engineers must use clear, descriptive titles for their Pull Requests (e.g., "Add Biometric Login" or "Fix Crash on Checkout").
    
- **The Automation:** When GitHub Actions creates the formal Release (in Step 5), it will be configured to use GitHub's native "generate release notes" feature. This aggregates the titles and links of all PRs merged since the previous version tag and bundles them into a clean, bulleted list.
    
- **The Result:** The final GitHub Release page will automatically contain the version number, the attached APK/IPA files, and a comprehensive, bulleted changelog representing all the work done.
    

# 4. Implementation Time Estimates

To transition the agency to this model, we must account for the initial DevOps setup, retrofitting our current projects, and the streamlined process for future work.

### Phase 1: The Initial Foundation (1 to 2 Weeks)

- **Scope:** A one-time, global setup cost for the agency.
    
- **Actions:** The CTO or Lead Dev researches, writes, and tests the definitive "Template" .yml workflows for GitHub Actions (handling both Android and iOS compilation). This includes configuring the certificate management approach (e.g., Fastlane Match for iOS provisioning profiles).
    

### Phase 2: Retrofitting Current Existing Repositories (2 to 4 Hours per Repo)

- **Scope:** Migrating active client projects to the new standard.
    
- **Actions:**
    
    - Restructure existing Git branches to strictly follow staging and production.
        
    - Copy the established GitHub Actions YAML templates into the .github/workflows directory of the repo.
        
    - Generate and inject the specific client’s Keystores/Certificates into the GitHub repository's "Secrets".
        
    - Run a test push to ensure artifacts generate correctly.
        

### Phase 3: Setting Up New Repositories (1 to 2 Hours per Repo)

- **Scope:** Bootstrapping a brand new client project pipeline.
    
- **Actions:**
    
    - Initialize the repo with staging and production branches from day one.
        
    - Copy-paste the template .yml workflow files.
        
    - Generate new App Store/Play Store signing keys and upload them to GitHub Secrets.
        
    - Create the corresponding tracking project and task in the internal Odoo instance.