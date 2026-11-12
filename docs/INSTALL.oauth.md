# OAuth setup (Google & GitHub)

Sign-in and OAuth are implemented in **FastAPI**, not in the frontend framework. The Vite SPA starts OAuth flows and relies on FastAPI redirect URIs and the `dr.api-token` httpOnly session cookie.

## Prerequisites

- Valid domain name (for production)
- `APP_SECRET` set on FastAPI backend and workers (see [`env.md`](./env.md))
- `NEXTAUTH_URL` set to the **public URL of the SPA** (legacy variable name; see [`env.md`](./env.md))

## Google OAuth setup

1. Visit the [Google Cloud Console](https://console.cloud.google.com).
2. Create a new project or select an existing one.
3. Navigate to **APIs & Services** → **Credentials**.
4. Click **Create Credentials** → **OAuth client ID**.
5. Select **Web application**.
6. Add **Authorized JavaScript origins**:
   - Vite dev: `http://localhost:5173`
   - Docker compose edge: `http://localhost:3000`
   - Production: `https://your-domain.com`
7. Add **Authorized redirect URIs** (FastAPI callbacks, not `/api/auth/...`):
   - Vite dev: `http://localhost:5173/fastapi/v0/account/auth/google/callback`
   - Compose: `http://localhost:3000/fastapi/v0/account/auth/google/callback`
   - Production: `https://your-domain.com/fastapi/v0/account/auth/google/callback`
8. Save the client ID and client secret.

## GitHub OAuth setup

1. Go to https://github.com/settings/developers.
2. Click **New OAuth App**.
3. Fill in application details:
   - **Homepage URL**: same origins as above (5173, 3000, or production).
   - **Authorization callback URL**:
     - Vite dev: `http://localhost:5173/fastapi/v0/account/auth/github/callback`
     - Compose: `http://localhost:3000/fastapi/v0/account/auth/github/callback`
     - Production: `https://your-domain.com/fastapi/v0/account/auth/github/callback`
4. Save the client ID and generate a client secret.

## Environment variables

Add these to the repo root `.env`:

```bash
# Google
AUTH_GOOGLE_ID=your_google_client_id
AUTH_GOOGLE_SECRET=your_google_client_secret

# GitHub
AUTH_GITHUB_ID=your_github_client_id
AUTH_GITHUB_SECRET=your_github_client_secret

# Public SPA URL (OAuth return_to, CORS) — required on backend/worker
NEXTAUTH_URL=http://localhost:5173   # or http://localhost:3000 for compose edge

# Session JWT signing (required; do not use NEXTAUTH_SECRET — use APP_SECRET)
APP_SECRET=your_random_secret_key
```

For local Vite dev, register **5173** callback URLs even if `NEXTAUTH_URL` is still `http://localhost:3000` for compose; the SPA sends `app_origin` on OAuth start. See [`vite_smoke_test_5173.md`](./vite_smoke_test_5173.md).

## Security notes

1. Never commit `.env` files to version control.
2. Generate `APP_SECRET` with a secure random generator.
3. Keep OAuth client secrets confidential and environment-specific.
4. Rotate secrets regularly in production.

## Troubleshooting

1. **Callback URL mismatch** — IdP redirect URIs must match FastAPI paths under `/fastapi/v0/account/auth/.../callback`.
2. **CORS errors** — Include the SPA origin in `CORS_ORIGINS` / `NEXTAUTH_URL` and any `CORS_ORIGINS_EXTRA` (e.g. `http://localhost:5173`).
3. **Session issues** — Confirm `APP_SECRET` is identical on API and workers; confirm cookies work (same-site `/fastapi` proxy in dev).

## Additional resources

- FastAPI auth routes: `packages/python/app/routes/account_auth.py`
- Google OAuth: https://developers.google.com/identity/protocols/oauth2
- GitHub OAuth: https://docs.github.com/en/developers/apps/building-oauth-apps
