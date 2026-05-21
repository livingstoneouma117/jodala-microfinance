# Deploy on Render (Domain: jodalamicrofinance.co.ke)

This project is now preconfigured for Render with [`render.yaml`](./render.yaml).

## What this setup does

- Deploys as a Render **Web Service** (Python runtime).
- Runs the app with `python app.py`.
- Initializes SQLite tables on startup from your app entrypoint.
- Stores SQLite at `/var/data/sacco.db` on a **persistent Render disk**.
- Registers custom domain `jodalamicrofinance.co.ke`.

## Important

- This config uses `plan: starter` and requires a billing method on Render.
- Demo seed data is disabled in production (`SEED_DEMO_DATA=false`).
- You must set bootstrap admin vars in Render env before first run:
  - `BOOTSTRAP_ADMIN_USERNAME`
  - `BOOTSTRAP_ADMIN_EMAIL`
  - `BOOTSTRAP_ADMIN_PASSWORD`
- Keep `SECRET_KEY` private (Render will generate one automatically from `render.yaml`).
- Root domain currently points to `102.209.117.206`. You will switch DNS to Render during step 6.

## 1) Push this project to GitHub

If Git is installed locally:

```bash
git init
git add .
git commit -m "Prepare Render deployment"
# create repo on GitHub, then:
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

## 2) Create service on Render

1. Log in to Render dashboard.
2. New -> Blueprint.
3. Connect your GitHub repo.
4. Confirm it detects `render.yaml`.
5. Create Blueprint.

Render will build and deploy the web service.

## 2.1) Set bootstrap admin env vars (first-time setup only)

In Render service -> Environment, set:

- `BOOTSTRAP_ADMIN_USERNAME` (example: `admin`)
- `BOOTSTRAP_ADMIN_EMAIL` (example: `admin@jodalamicrofinance.co.ke`)
- `BOOTSTRAP_ADMIN_PASSWORD` (strong password you will use to sign in)

On first startup, if the database has no users, the app creates this admin account automatically.

## 3) Confirm app is up on onrender URL

Open the generated `https://<service-name>.onrender.com/api/health` and confirm JSON contains `"status":"ok"`.

## 4) Add custom domain in Render

In service settings -> Custom Domains, confirm:

- `jodalamicrofinance.co.ke`
- (Render auto-manages `www` redirect for root domains)

## 5) Update DNS records

Your DNS provider is authoritative at:

- `dan1.host-ww.net`
- `dan2.host-ww.net`

Set records as follows (per Render docs):

- Root domain (`@`):
  - Preferred: `ANAME` or `ALIAS` -> your Render subdomain (e.g. `jodala-microfinance.onrender.com`)
  - Fallback: `A` -> `216.24.57.1`
- `www`: `CNAME` -> your Render subdomain
- Remove conflicting `AAAA` record(s) if any exist.

## 6) Verify domain in Render

Back in Render Custom Domains, click **Verify**.

Render then provisions TLS automatically and redirects HTTP -> HTTPS.

## 7) Final checks

```bash
curl -I https://jodalamicrofinance.co.ke
curl https://jodalamicrofinance.co.ke/api/health
```

Expected: health response with `"status":"ok"`.
