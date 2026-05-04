# Geckode — Web

The Next.js 14 dashboard for Geckode. Sign in with GitHub, connect a repo,
review pull requests on demand, and edit per-repo review standards — without
ever touching a webhook URL, a `/review` comment, or a YAML file.

## Stack

- **Next.js 14** (App Router) + **TypeScript**
- **Tailwind CSS** + **shadcn/ui** primitives (Radix UI under the hood)
- **NextAuth.js** for GitHub OAuth (scopes: `read:user`, `user:email`, `repo`,
  `admin:repo_hook`)
- Talks to the **Geckode FastAPI backend** (`backend/`) over HTTP using the
  signed-in user's GitHub access token as a Bearer token.

## Pages

| Route                                  | Purpose                                                                 |
| -------------------------------------- | ----------------------------------------------------------------------- |
| `/`                                    | Landing — hero, features, "Continue with GitHub" CTA.                   |
| `/dashboard`                           | All connected repos as cards, plus a "Connect a repository" dialog.     |
| `/repos/[owner]/[repo]`                | Open PRs list with a per-PR "Review" button + optional instructions.    |
| `/repos/[owner]/[repo]/settings`       | Per-repo review configuration: language, strictness, team standards.    |

The connect dialog auto-loads your GitHub repos via `/api/github/repos`. It
calls a Server Action that registers the webhook on the backend on your
behalf — the URL is never exposed in the UI.

## Logo / favicon

Put your **`public/logo.png`** in this folder (same directory as this README: `frontend/public/logo.png`). It is served at **`/logo.png`** and copied to **`src/app/icon.png`** and **`apple-icon.png`** on `npm run dev` and `npm run build` so Next.js can use it as the favicon. No file outside the frontend directory is required.

## Local development

1. Install dependencies:

   ```bash
   cd frontend
   npm install
   ```

   (If your clone has `testings/frontend`, `cd` there instead.)

2. Create a `.env.local` from the template:

   ```bash
   cp .env.example .env.local
   ```

   Fill in:

   - `NEXTAUTH_SECRET` — `openssl rand -base64 32`
   - `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` — a GitHub OAuth App whose
     **Authorization callback URL** is
     `http://localhost:3000/api/auth/callback/github`. You can reuse the
     OAuth app the FastAPI backend uses if you add this second callback URL
     to it.
   - `GECKODE_API_URL` — base URL of the FastAPI backend (e.g.
     `http://localhost:8080`). The frontend will forward the GitHub OAuth
     access token as `Authorization: Bearer …` on every API call.

3. Make sure the backend is running with the same `FRONTEND_ORIGIN` value
   you used for `NEXTAUTH_URL` (e.g. `FRONTEND_ORIGIN=http://localhost:3000`).

4. Start the dev server:

   ```bash
   npm run dev
   ```

   Open [http://localhost:3000](http://localhost:3000).

## Deploying to Vercel

1. Import the repo and set Vercel **Root Directory** to the Next.js app
   (e.g. `frontend` or `testings/frontend` depending on your repository layout).
2. Add the env vars from `.env.example`. `NEXTAUTH_URL` should be the
   production URL (e.g. `https://geckode.vercel.app`).
3. Update the GitHub OAuth App's callback URL to
   `https://your-domain/api/auth/callback/github`.
4. Make sure `GECKODE_API_URL` points at the public URL of your FastAPI
   backend (Koyeb / **AWS Elastic Beanstalk** / etc.). The backend's
   `FRONTEND_ORIGIN` should include your Vercel domain so CORS allows the
   browser to talk to the backend on user-side fetches if you ever switch
   any of these calls to client-side.

## Backend changes this UI relies on

This frontend talks to the FastAPI app in `../backend/` (sibling folder) plus two
small additions made in the same change:

- `current_user_id` now also accepts `Authorization: Bearer <github_token>`
  and upserts the matching `User` row (so NextAuth-issued tokens can drive
  the same API the legacy session UI uses).
- `POST /api/repos/{owner}/{repo}/pulls/{pr_number}/review` triggers the
  same review pipeline as the `/review` PR comment, with optional
  `{"instructions": "..."}` extra prompt.
