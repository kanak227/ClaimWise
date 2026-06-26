# Deployment Guide: Vercel & Render (Free Tier)

This guide walks you through deploying the complete ClaimWise application on free tiers using **Vercel** for the React frontend, **Render** for the containerized FastAPI backend, and **Supabase** for the PostgreSQL database.

---

## Architecture Overview

```
[React Frontend (Vercel)]
         │
         ▼ (API requests over HTTPS)
[FastAPI Backend + Pathway (Render Docker)]
         │
         ▼ (Data Persistence)
[PostgreSQL Database (Supabase)]
```

---

## Step 1: Deploy a Free PostgreSQL Database on Supabase

Render's free database tier expires after 90 days. Using **Supabase** gives you a free managed PostgreSQL instance that does not expire.

1.  Sign up or log in at [Supabase.com](https://supabase.com/).
2.  Click **New Project** and configure:
    *   **Project Name**: `claimwise-db`
    *   **Database Password**: *(Save this password)*
    *   **Region**: Select a region close to your target audience.
3.  Once the project is provisioned (takes 1–2 minutes), navigate to **Project Settings** (gear icon) -> **Database**.
4.  Scroll down to **Connection string** and copy the **URI** format:
    ```
    postgresql://postgres.[username]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
    ```
    *Replace `[password]` with your actual database password.*

---

## Step 2: Deploy the FastAPI Backend to Render

Render will build and deploy the backend automatically using the `backend/Dockerfile` configurations.

1.  Push your ClaimWise repository to your **GitHub** account.
2.  Log in to [Render.com](https://render.com/).
3.  Click **New +** at the top right and select **Web Service**.
4.  Choose **Build and deploy from a Git repository**, connect your GitHub account, and select your `ClaimWise` repository.
5.  On the creation form, configure the following values:
    *   **Name**: `claimwise-backend`
    *   **Language**: `Docker`
    *   **Docker Build Context**: `.` *(This must be the repository root to copy the `ml/` folder)*
    *   **Dockerfile Path**: `backend/Dockerfile`
    *   **Instance Type**: `Free`
6.  Click **Advanced** and add the following **Environment Variables**:
    *   `GEMINI_API_KEY`: *(Your Google Gemini API Key)*
    *   `DATABASE_URL`: *(Your Supabase PostgreSQL connection URI)*
    *   `PYTHONUNBUFFERED`: `1`
7.  Click **Create Web Service**.
    *   *Render will build the Docker container (installing Python, Tesseract-OCR, and Pathway) and deploy it. Once complete, it will provide a live URL like `https://claimwise-backend.onrender.com`.*

---

## Step 3: Deploy the React Frontend to Vercel

Vercel will build the frontend React application from the static configurations.

1.  Log in to [Vercel.com](https://vercel.com/).
2.  Click **Add New...** -> **Project**.
3.  Import your `ClaimWise` GitHub repository.
4.  On the **Configure Project** page:
    *   **Framework Preset**: Select `Vite` (or leave as auto-detected).
    *   **Root Directory**: Click Edit and select the `frontend` folder.
5.  Expand the **Environment Variables** section and add:
    *   **Key**: `VITE_API_BASE_URL`
    *   **Value**: `https://claimwise-backend.onrender.com` *(Replace with your live Render backend URL)*
6.  Click **Deploy**.
    *   *Vercel will run `pnpm build` and generate your static site. Once completed, you will receive a production URL like `https://claimwise-frontend.vercel.app`.*

---

## Step 4: Verification & Integration Testing

1.  **Backend Health**: Navigate to `https://claimwise-backend.onrender.com/health` in your browser. It should return:
    ```json
    {"status":"healthy","service":"Claims Agent API"}
    ```
2.  **Frontend Interface**: Open your Vercel URL. Upload files, create routing rules, and verify that the claim queues re-arrange dynamically using Pathway.
