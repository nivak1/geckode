# Geckode

## Layout

| Path | What |
|------|------|
| [`frontend/`](frontend/) | Next.js 14 dashboard (Vercel). Brand logo: `frontend/public/logo.png`. |
| [`backend/`](backend/) | FastAPI + review worker (Docker / AWS EB / Koyeb / etc.). |

## Backend deploy notes

- **Dockerfile** is under `backend/`; build with **context** = `backend/` (directory that contains `server.py`).
- The container listens on **`PORT`** if set, otherwise **8080** (Elastic Beanstalk and other hosts often inject `PORT`).
- **Production DB:** set `DATABASE_URL` to your Postgres URI (e.g. Supabase). You do **not** ship `geckode.db`.
- **Local dev:** omit `DATABASE_URL` or point at `sqlite:///./geckode.db` — SQLite file is created beside `server.py`, is listed in `.gitignore` (`*.db`), and is optional once you use Postgres.
