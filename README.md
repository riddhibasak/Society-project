# Society Maintenance Tracker

Full-stack tracker for apartment-society maintenance, with resident and administrator roles.

## Live Deployment Links

- **Frontend Application (Vercel)**: [https://society-project.vercel.app](https://society-project.vercel.app)
- **Backend API (Render)**: [https://society-maintenance-api-9bun.onrender.com](https://society-maintenance-api-9bun.onrender.com)
- **API Documentation**: [https://society-maintenance-api-9bun.onrender.com/docs](https://society-maintenance-api-9bun.onrender.com/docs)

---

## Seeded Accounts (Demo & Testing)

- **Admin Account**: `admin@demo.example.com` / `Admin123!` *(or `admin@society.com` / `admin123`)*
- **Resident Account**: `resident@demo.example.com` / `Resident123!`

---

## Local run

1. Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`. Keep `SEED_DEMO=true` only locally; use `false` in production.
2. Start PostgreSQL: `docker compose up -d db`
3. Backend: `cd backend; python -m venv .venv; .\.venv\Scripts\activate; pip install -r requirements.txt; uvicorn app.main:app --reload`
4. Frontend: `cd frontend; npm install; npm run dev`

Open `http://localhost:3000`; API documentation is at `http://localhost:8000/docs`.

---

## Public deployment

### 1. Frontend (Vercel)
Root-level build configurations are included in `package.json` and `vercel.json`:
- **Build & Install Commands**: Pre-configured to build the Next.js `frontend` directory directly from repository root.
- **Environment Variable**: `NEXT_PUBLIC_API_URL` set to the live backend URL (`https://society-maintenance-api-9bun.onrender.com`).

### 2. Backend (Render / Railway)
Create a managed PostgreSQL database on Railway or Render and apply `backend/migrations/001_initial.sql` once. Deploy `backend` as a Python web service using:
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment Variables**: Set from `backend/.env.example`, especially a strong `SECRET_KEY`, `DATABASE_URL` (with `sslmode=require`), `CORS_ORIGINS`, and `SEED_DEMO=true`.

Email is optional: configure Resend variables to enable notifications. Photo uploads are stored locally by default; use a persistent disk or replace `save_upload` with Cloudinary/Supabase storage for production.
