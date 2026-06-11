
## Overview

This upgrade aims to aggregate tasks from Notion, Odoo, and ERPNext into a central hub deployed on Vercel, which then acts as the single source of truth for the Life Tracker Flutter app. **n8n** will serve as the ETL (Extract, Transform, Load) orchestration layer.

## Architecture Stack

- **Data Sources:** Notion (API), Odoo (XML-RPC/REST), ERPNext (REST/Webhooks).
    
- **Orchestration:** n8n (Self-hosted or Cloud).
    
- **Central Hub:** Vercel (Next.js API routes or pure Node.js Serverless functions) + Database (Vercel Postgres or Supabase).
    
- **Frontend:** Existing Flutter app (Hive for local caching).
    

## Phase 1: The Vercel Central Hub & Unified Schema

This phase involves setting up the central database and the APIs that will communicate with both your n8n orchestrator and your Flutter app.

### Task 1.1: Project Setup & Database Provisioning

- **Action:** Initialize a Next.js project (using App Router for API endpoints) and deploy it to Vercel. Provision a Vercel Postgres database directly from the Vercel Dashboard and link it to your project to get the environment variables (`POSTGRES_URL`).
    
- **Technical Guidance:** Use a lightweight ORM like **Prisma** or **Drizzle**. They provide excellent type-safety and make the upsert logic much easier to write than raw SQL.
    
- **Acceptance Criteria:** * Next.js application is successfully deployed and reachable.
    
    - Postgres database is accessible and ORM is configured locally and in production.
        
- **Dependencies:** None.
    
- **Expected Duration:** 1 hour.
    

### Task 1.2: Define the Unified Schema & Run Migrations

- **Action:** Create your database schema (e.g., `schema.prisma`) normalizing the data from all three platforms.
    
- **Fields Required:**
    
    - `id` (UUID - Primary Key, default to auto-generate)
        
    - `source_system` (Enum/String: `notion`, `odoo`, `erpnext`)
        
    - `source_id` (String - The original ID from the source platform)
        
    - `title` (String)
        
    - `markdown_text` (Text - nullable, stores the content/description of the task)
        
    - `status` (String - mapped to a standard: e.g., `pending`, `in_progress`, `completed`)
        
    - `due_date` (DateTime - nullable, the original due date provided by the source platform)
        
    - `internal_due_date` (DateTime - nullable. Not synced whatsoever; manually set internally by the user)
        
    - `last_synced_at` (DateTime - default to `now()`)
        
- **Technical Guidance:** Create a **Composite Unique Constraint** on `@@unique([source_system, source_id])`. This is critical. It guarantees you won't get duplicate tasks if n8n syncs the same Odoo task twice, and it acts as the target for your `Upsert` operations.
    
- **Acceptance Criteria:**
    
    - Migration executes successfully.
        
    - Attempting to insert two records with the same `source_system` and `source_id` throws a constraint error.
        
- **Dependencies:** Task 1.1.
    
- **Expected Duration:** 1 hour.
    

### Task 1.3: Build the Sync API (`POST /api/tasks/sync`)

- **Action:** Create the endpoint that n8n will hit whenever a task is created or updated in your connected platforms.
    
- **Technical Guidance:** * **Security:** Require a secret Bearer token in the `Authorization` header and verify it against an environment variable (e.g., `process.env.SYNC_API_KEY`).
    
    - **Logic:** Use Prisma's `upsert` function. Search by the composite key `(source_system, source_id)`. If found, `update` the title, markdown_text, status, due_date, and last_synced_at (explicitly ensure `internal_due_date` is excluded from the update payload so local changes aren't overwritten). If not found, `create` a new record.
        
    - **Batching:** Design the endpoint to accept an array of tasks `[{task1}, {task2}]` rather than a single object, to reduce API calls from n8n.
        
- **Acceptance Criteria:**
    
    - Reject requests without valid Bearer tokens (HTTP 401).
        
    - Payload arrays are successfully parsed, inserted, or updated in the Postgres DB.
        
- **Dependencies:** Task 1.2.
    
- **Expected Duration:** 2 to 3 hours.
    

### Task 1.4: Build the Mobile Fetch API (`GET /api/tasks`)

- **Action:** Create the endpoint your Flutter app will query to get the master task list.
    
- **Technical Guidance:** * **Delta Syncing (Crucial for Speed):** Don't fetch the entire database every time the app opens. Accept a query parameter `?updated_after=TIMESTAMP`.
    
    - Your Flutter app will pass the timestamp of its last successful sync. The Vercel API should only return tasks where `last_synced_at > updated_after`.
        
- **Acceptance Criteria:**
    
    - Returns JSON array of tasks.
        
    - If `updated_after` is provided, only returns records with a newer `last_synced_at` timestamp.
        
- **Dependencies:** Task 1.2.
    
- **Expected Duration:** 1.5 hours.
    

## Phase 2: The n8n Orchestration Layer (The "Glue")

This phase involves building the n8n workflows that connect the three platforms to your Vercel API.

### Task 2.1: Notion Pipeline

- **Action:** Create workflow with Schedule Trigger (e.g., every 15 mins). Search for recently updated pages in your Notion Task Database. Transform Notion properties (Name, Markdown Content, Status, Date) to the Unified Schema. Send a POST request to your Vercel `/api/tasks/sync` endpoint.
    
- **Acceptance Criteria:** Updating a task in Notion successfully creates/updates the record in the Vercel Postgres DB within 15 minutes.
    
- **Dependencies:** Task 1.3.
    
- **Expected Duration:** 2 hours.
    

### Task 2.2: ERPNext Pipeline

- **Action:** Add Webhook Node in n8n. In ERPNext, configure a webhook that fires "On Save" for the `Task` DocType, sending the payload to the n8n webhook URL. Map fields (`subject`, `description` to `markdown_text`, `status`, `exp_end_date`) to the Unified Schema. Send HTTP request to Vercel API.
    
- **Acceptance Criteria:** Saving a task in ERPNext instantly updates the record in the Vercel Postgres database via the webhook.
    
- **Dependencies:** Task 1.3.
    
- **Expected Duration:** 1.5 hours.
    

### Task 2.3: Odoo Pipeline

- **Action:** In Odoo, use an Automated Action with a Webhook to n8n for `project.task` on Creation & Update. Map fields (`name`, `description` to `markdown_text`, `stage_id`, `date_deadline`) in n8n to the Unified Schema. Send HTTP request to Vercel API.
    
- **Acceptance Criteria:** Dragging a task to a new stage in Odoo instantly updates the status in the Vercel Postgres database.
    
- **Dependencies:** Task 1.3.
    
- **Expected Duration:** 1.5 hours.
    

## Phase 3: Mobile App Integration (Flutter)

We want to maintain the app's blazing-fast speed by keeping the "local-first" feel.

### Task 3.1: Update Local Storage (Hive)

- **Action:** Create a new `TaskItem` Hive model in Flutter that mirrors the Unified Schema (including `markdown_text` and `internal_due_date`). Create a `task_box` in Hive to store these locally.
    
- **Acceptance Criteria:** TypeAdapter successfully generated and registered. Hive box opens without errors on app startup.
    
- **Dependencies:** None (Can be done in parallel).
    
- **Expected Duration:** 1 hour.
    

### Task 3.2: Create the `TaskSyncService`

- **Action:** Build a service that calls the `GET /api/tasks` Vercel endpoint in the background, utilizing the `updated_after` parameter based on the last stored sync time. Save fetched tasks to the local Hive `task_box`.
    
- **Acceptance Criteria:** App successfully fetches new tasks silently in the background and stores them locally without overwriting unchecked local changes (if any).
    
- **Dependencies:** Task 1.4, Task 3.1.
    
- **Expected Duration:** 2.5 hours.
    

### Task 3.3: UI Updates

- **Action:** Add a "Tasks" panel to the Minimalist Dashboard. Add visual indicators (small platform icons) to show whether a task originated from Notion, Odoo, or ERPNext. Add a detail view to display `markdown_text` and a date picker for the `internal_due_date`.
    
- **Acceptance Criteria:** UI correctly renders tasks reading _only_ from the local Hive box (ensuring offline capability). Icons map correctly to the `source_system` string.
    
- **Dependencies:** Task 3.1.
    
- **Expected Duration:** 2 hours.
    

## Phase 4: Bi-Directional Sync (Post-MVP)

Eventually, checking off a task in the Flutter app should complete it in Notion/Odoo/ERPNext.

### Task 4.1: Flutter Outbound Sync

- **Action:** When user checks off a task, update local Hive box immediately (optimistic UI), then send a `POST /api/tasks/update` to Vercel.
    
- **Acceptance Criteria:** App handles offline states gracefully (queues update if offline and sends when reconnected). UI feels instant to the user.
    
- **Dependencies:** Task 3.2.
    
- **Expected Duration:** 2 hours.
    

### Task 4.2: Vercel Webhook Router

- **Action:** Create Vercel endpoint to accept status updates from Flutter. Update Postgres DB, then fire an outgoing Webhook to a specific n8n "Update Router" workflow.
    
- **Acceptance Criteria:** Vercel correctly passes the `source_id`, `source_system`, and new `status` to n8n.
    
- **Dependencies:** Task 4.1.
    
- **Expected Duration:** 1.5 hours.
    

### Task 4.3: n8n Reverse Router Workflow

- **Action:** The n8n workflow receives Vercel's webhook and uses a Switch Node to check the `source_system` variable.
    
    - If `notion`: Update Notion Page property to "Done".
        
    - If `erpnext`: Update Task status via API.
        
    - If `odoo`: Move task to a "Done" stage via API.
        
- **Acceptance Criteria:** Checking a task in Flutter results in the task visibly moving to "Done" in the original source platform within seconds.
    
- **Dependencies:** Task 4.2.
    
- **Expected Duration:** 3 hours.