
# Docker Stack — Unified Hub + Scheduler + Nginx (HTTPS + optional mTLS)

This stack runs:
- **hub**: Unified FastAPI app (UI + API)
- **scheduler**: Daily/Hourly automation (v12+)
- **nginx**: HTTPS reverse proxy with optional **mTLS**

## Prereqs
- Your project repo at the same level as this stack (compose mounts `./` to `/app`)
- Valid TLS cert/key in `nginx/certs` (self-signed OK for testing)

## Quick start
```bash
cp .env.example .env
# Edit .env: set HUB_API_KEY, set NGINX_SERVER_NAME, and point cert paths (inside container paths are fine).
docker compose build
docker compose up -d
```

Open **https://<NGINX_SERVER_NAME>/**

## Optional: enable mTLS
- Put your CA certificate at `nginx/certs/ca.crt`
- In `.env`, set `ENABLE_MTLS=true`
- Restart nginx: `docker compose restart nginx`

## Notes
- Data persists under Docker volume `hub_data` (mounted to `/app/data`).
- The app still enforces API key auth and rate limiting.
- The scheduler runs your morning/close/hourly jobs as configured in code.
