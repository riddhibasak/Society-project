# Society Maintenance Tracker

Full-stack tracker for apartment-society maintenance, with resident and administrator roles.

## Local run

1. Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`. Keep `SEED_DEMO=true` only locally; use `false` in production.
2. Start PostgreSQL: `docker compose up -d db`
3. Backend: `cd backend; python -m venv .venv; .\.venv\Scripts\activate; pip install -r requirements.txt; uvicorn app.main:app --reload`
4. Frontend: `cd frontend; npm install; npm run dev`

Open `http://localhost:3000`; API documentation is at `http://localhost:8000/docs`.

Seeded accounts (development only): `admin@demo.example.com` / `Admin123!`, `resident@demo.example.com` / `Resident123!`.

## Public deployment

Create a managed PostgreSQL database on Railway or Render and apply `backend/migrations/001_initial.sql` once. Deploy `backend` as a Python web service using
`pip install -r requirements.txt` and `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set its environment
variables from `backend/.env.example`, especially a strong `SECRET_KEY`, `DATABASE_URL`, and `CORS_ORIGINS`.

Deploy `frontend` on Vercel. Set `NEXT_PUBLIC_API_URL` to the public backend URL, then redeploy. Finally set
the backend `CORS_ORIGINS` to the Vercel URL. Do not use the demo credentials or default secret in production.

Email is optional: configure Resend variables to enable notifications. Photo uploads are stored locally by default;
use a persistent disk or replace `save_upload` with Cloudinary/Supabase storage for production.
