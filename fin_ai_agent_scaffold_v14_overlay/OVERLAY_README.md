
# v14 Overlay (Unified Hub + Scopes + mTLS + systemd)

This overlay adds:
- Unified FastAPI app (`agent/app/server.py`) that serves both UI and the Hub API
- Scope enforcement via `HUB_API_SCOPES`
- Basic mTLS deployment notes + systemd unit files

## Apply
From your project root:
```bash
unzip -o fin_ai_agent_scaffold_v14_overlay.zip -d .
echo 'pydantic>=2.8
python-multipart>=0.0.9' >> requirements.txt
```

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export HUB_API_KEY="CHANGE_THIS_LONG_RANDOM_KEY"
# Optional scopes mapping:
# export HUB_API_SCOPES='{"CHANGE_THIS_LONG_RANDOM_KEY":["rd.run","rd.crisis","kb.read","kb.write","smartsauce.write","terry.harvest","events.read"]}'
uvicorn agent.app.server:app --host 127.0.0.1 --port 8010
```

## systemd
See files under `deploy/`. Enable as user services: `hub@<user>.service` and `scheduler@<user>.service`.
