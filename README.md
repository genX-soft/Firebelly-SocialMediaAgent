HEAD
# Firebelly-SocialMediaAgent
=======
# AutoSocial - Social Media Management Tool

AutoSocial is a premium web application for managing social media accounts, scheduling posts, and interacting with audiences on Facebook and Instagram.

## Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **PostgreSQL** (running locally)
- **ngrok** (for local webhook development)
- **Meta App Credentials** (App ID, Secret, and Webhook configuration)

## Setup and Installation

### 1. Environment Configuration

Create a `.env` file in the root directory (copy from `.env.example`). Ensure the following values are set correctly:

- `DATABASE_URL`: Your local PostgreSQL connection string.
- `META_APP_ID` & `META_APP_SECRET`: From your Meta App dashboard.
- `NGROK_AUTHTOKEN`: From your ngrok dashboard.
- `VITE_API_BASE_URL`: Your public ngrok tunnel URL.

### 2. Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

### 3. Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```

### 4. Webhook Tunneling (Critical)

For the real-time inbox and scheduling features to work properly during local development, you MUST start an ngrok tunnel to your backend port (8000):

```bash
ngrok http 8000
```

Update the `VITE_API_BASE_URL` in your frontend configuration and the Meta Webhook URL in the Meta Dashboard with the generated ngrok URL.

## Features

- **Multi-Platform Posting**: Post to Facebook Pages and Instagram Business accounts simultaneously.
- **Precision Scheduling**: Schedule posts for future publication with a background worker.
- **Unified Inbox**: Real-time interaction management for FB comments, IG comments, and DMs.
- **Premium UI**: Modern dark theme with glassmorphism and real-time updates.
