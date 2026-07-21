# ConditionWatch backend

Production-shaped FastAPI backend for authenticated multi-user camera watch sessions.

## Features

- Email/password accounts with Argon2 hashes and signed JWT bearer tokens
- Browser-based mobile login that returns to `conditionwatch://auth`
- Per-user device ownership and FCM token rotation
- OpenAI audio transcription and structured condition normalization
- Multimodal Responses API evaluation of ephemeral JPEG frames
- Confidence thresholding, transactional match deduplication, and high-priority data-only FCM
- No raw camera-frame retention; only decision metadata is stored
- PostgreSQL deployment plus SQLite local fallback

## Local setup

```bash
cd backend
cp .env.example .env
```

Set at minimum:

```dotenv
OPENAI_API_KEY=...
JWT_SECRET=<at least 32 random characters>
```

For Firebase outside Google Cloud, download a service-account key from Firebase Project Settings, keep it under `backend/secrets/`, uncomment the read-only Docker volume, and set:

```dotenv
GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/firebase-service-account.json
FIREBASE_PROJECT_ID=your-firebase-project-id
```

Never commit that key. On Cloud Run/GKE, grant the runtime service account Firebase Cloud Messaging permissions and use Application Default Credentials instead.

Run with Docker:

```bash
docker compose up --build
```

Or run locally with SQLite:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
mkdir -p data
uvicorn app.main:app --reload
```

Swagger UI: `http://localhost:8000/docs`

## Android connection

Deploy behind HTTPS, then set Android `API_BASE_URL` to the public URL with a trailing slash and set `DEMO_MODE=false`. The web login URL is derived from the same base URL.

## Privacy and operations

Frames are sent to OpenAI for evaluation but never stored by this service. OpenAI response storage defaults off. Production should add database migrations, managed secrets, HTTPS termination, request-level observability without frame bodies or tokens, backups, retention cleanup for evaluation metadata, and load tests based on the configured sampling interval.
