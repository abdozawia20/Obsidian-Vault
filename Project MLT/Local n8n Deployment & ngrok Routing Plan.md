
This guide will initialize a lightweight, router-only instance of n8n on your TUXEDO OS machine and securely expose it to the internet using a persistent ngrok tunnel, utilizing a `.env` file for secure configuration.

## Step 1: Claim Your Static ngrok Domain

Before writing any code, we need your persistent public URL.

1. Log into your account at [dashboard.ngrok.com](https://dashboard.ngrok.com/ "null").
    
2. On the left sidebar, navigate to **Domains**.
    
3. Click **Create Domain** or "Claim free static domain". ngrok will assign you a permanent URL (e.g., `heroic-panda-tightly.ngrok-free.app`).
    
4. Navigate to **Authtokens** on the sidebar and copy your unique Auth Token.
    

## Step 2: Create the Configuration Files

Instead of installing ngrok directly on your host OS, we will run both n8n and ngrok as Docker containers. We will use a `.env` file to securely store credentials.

1. Open your terminal on the TUXEDO server:
    
    ```
    mkdir ~/n8n-router
    cd ~/n8n-router
    ```
    
2. Create the `.env` file. This file holds all your sensitive data and custom variables:
    
    ```
    nano .env
    ```
    
    Paste the following and replace the placeholders with your actual details:
    
    ```
    # --- n8n Configuration ---
    GENERIC_TIMEZONE=Europe/Istanbul
    WEBHOOK_URL=https://<YOUR-STATIC-DOMAIN>.ngrok-free.app
    N8N_BASIC_AUTH_USER=<CHOOSE_A_USERNAME>
    N8N_BASIC_AUTH_PASSWORD=<CHOOSE_A_SECURE_PASSWORD>
    
    # --- ngrok Configuration ---
    NGROK_AUTHTOKEN=<YOUR_NGROK_AUTH_TOKEN>
    NGROK_DOMAIN=<YOUR-STATIC-DOMAIN>.ngrok-free.app
    ```
    
    Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).
    
3. Create the `docker-compose.yml` file:
    
    ```
    nano docker-compose.yml
    ```
    
    Paste the following configuration. Notice how it now dynamically pulls from your `.env` file:
    
    ```
    version: '3.8'
    
    services:
      n8n:
        image: docker.n8n.io/n8nio/n8n
        container_name: n8n_router
        restart: unless-stopped
        ports:
          - "5678:5678" # Keep local access available for debugging
        env_file:
          - .env
        environment:
          # ⚠️ Optimization: Don't save successful logs to keep the DB tiny
          - EXECUTIONS_DATA_SAVE_ON_SUCCESS=none
          - EXECUTIONS_DATA_PRUNE=true
          - EXECUTIONS_DATA_MAX_AGE=24
          - N8N_BASIC_AUTH_ACTIVE=true
        volumes:
          - n8n_data:/home/node/.n8n
    
      ngrok:
        image: ngrok/ngrok:latest
        container_name: ngrok_tunnel
        restart: unless-stopped
        depends_on:
          - n8n
        env_file:
          - .env
        # This command maps the ngrok tunnel directly to the internal n8n container
        command:
          - "http"
          - "n8n:5678"
          - "--domain=${NGROK_DOMAIN}"
    
    volumes:
      n8n_data:
    ```
    
    Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).
    

## Step 3: Initialize and Verify

1. Start the services in the background:
    
    ```
    docker compose up -d
    ```
    
2. Verify the tunnel is active by visiting `https://<YOUR-STATIC-DOMAIN>.ngrok-free.app` in your web browser.
    
3. Log in using the Basic Auth credentials you set in the `.env` file. You are now looking at your live n8n canvas!
    

## Step 4: Link n8n to Vercel (Phase 2 Readiness)

Now that n8n is live and public, you can establish the connections for Phase 2:

### A. Routing TO Vercel (Outbound)

Inside n8n, whenever you want to push a task to your central hub:

1. Add an **HTTP Request** node.
    
2. Set the Method to `POST` and the URL to `https://<YOUR-VERCEL-APP>.vercel.app/api/tasks/sync`.
    
3. Under Authentication, select "Header Auth" and pass your `SYNC_API_KEY` (as defined in Task 1.3 of the PRD).
    

### B. Routing FROM Vercel (Inbound)

For Phase 4 (Bi-directional sync), Vercel needs to tell n8n when you check off a task on your phone.

1. In n8n, create a new workflow and add a **Webhook** trigger node.
    
2. Ensure the HTTP Method is `POST`.
    
3. Copy the "Production URL" from the node. It will look like: `https://<YOUR-STATIC-DOMAIN>.ngrok-free.app/webhook/random-uuid`
    
4. Add this exact URL as an environment variable in your Vercel dashboard (e.g., `N8N_WEBHOOK_URL`). Your Next.js API will send payloads here.
    

### C. Local Routing FROM ERPNext

Because n8n and ERPNext are on the exact same TUXEDO server, ERPNext doesn't even need to use the ngrok URL! In ERPNext's Webhook settings, simply point it to `http://127.0.0.1:5678/webhook/your-n8n-path`. It will trigger instantly with zero internet latency.