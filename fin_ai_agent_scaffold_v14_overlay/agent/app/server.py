from fastapi import FastAPI, Depends, Request, HTTPException, Header
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import json, asyncio

from ..hub.security import verify_api_key, verify_hmac_signature, check_ip, read_limiter, write_limiter, require_scopes
from ..orchestrator.runtime import analyze_ticker, crisis_watch
from ..terry.harvester import harvest
from ..smartsauce.version_store import StoreConfig, store_version
from ..smartsauce.diff import compare_versions
from ..smartsauce.reports import write_report
from ..db.knowledge import init_db, insert_event, latest_events, latest_summaries
from ..core.config import ensure_config, load_yaml
from ..hub.models import AnalyzeReq, AnalyzeResp, CrisisReq, HarvestReq, StoreVersionReq, CompareReq, DailySummaryReq

app = FastAPI(title="Unified Hub + UI", version="1.0")
templates = Jinja2Templates(directory=str(__file__).replace('server.py','templates'))

def auth_dependency(request: Request, x_api_key: str = Header(None), x_signature: str = Header(None), scopes: str = ""):
    remote_ip = request.client.host if request.client else "unknown"
    if not check_ip(remote_ip):
        raise HTTPException(status_code=403, detail="Forbidden IP")
    if not x_api_key or not verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API Key")
    body = request.scope.get("body_bytes", b"")
    if not verify_hmac_signature(x_api_key, body, x_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    request.state.api_key = x_api_key
    request.state.scopes = set(scopes.split(",")) if scopes else set()
    return True

@app.middleware("http")
async def capture_body(request: Request, call_next):
    body = await request.body()
    request.scope["body_bytes"] = body
    response = await call_next(request)
    return response

def get_cfg():
    return load_yaml(ensure_config())

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    cfg = get_cfg(); eng = init_db(cfg['database']['path'])
    events = latest_events(eng, limit=100)
    summaries = latest_summaries(eng, limit=7)
    return templates.TemplateResponse('index.html', {'request': request, 'events': events, 'summaries': summaries})

@app.post("/api/v1/rd/analyze", response_model=AnalyzeResp)
def rd_analyze(req: AnalyzeReq, request: Request, _=Depends(auth_dependency)):
    if not require_scopes(request.state.api_key, {"rd.run"}):
        raise HTTPException(status_code=403, detail="Missing scope rd.run")
    if not write_limiter.allow(request.state.api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    out = analyze_ticker(ticker=req.ticker, strategy=req.strategy,
                         user_summary=req.user_summary, llm_summary=req.llm_summary, automation_summary=req.automation_summary)
    cfg = get_cfg(); eng = init_db(cfg['database']['path'])
    insert_event(eng, "HubAPI", "CALL", json.dumps({"route":"/rd/analyze","payload":req.model_dump()}))
    return AnalyzeResp(tag=out['tag'], metrics=out['metrics'], disclaimer=out['disclaimer'])

@app.post("/api/v1/rd/crisis-watch")
def rd_crisis(req: CrisisReq, request: Request, _=Depends(auth_dependency)):
    if not require_scopes(request.state.api_key, {"rd.crisis"}):
        raise HTTPException(status_code=403, detail="Missing scope rd.crisis")
    if not read_limiter.allow(request.state.api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    t = req.ticker or "SPY"
    out = crisis_watch(ticker=t)
    cfg = get_cfg(); eng = init_db(cfg['database']['path'])
    insert_event(eng, "HubAPI", "CALL", json.dumps({"route":"/rd/crisis-watch","payload":req.model_dump()}))
    return out

@app.post("/api/v1/terry/harvest")
def terry_harvest(req: HarvestReq, request: Request, _=Depends(auth_dependency)):
    if not require_scopes(request.state.api_key, {"terry.harvest"}):
        raise HTTPException(status_code=403, detail="Missing scope terry.harvest")
    if not write_limiter.allow(request.state.api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    inserted = harvest()
    cfg = get_cfg(); eng = init_db(cfg['database']['path'])
    insert_event(eng, "HubAPI", "CALL", json.dumps({"route":"/terry/harvest","payload":req.model_dump()}))
    return {"inserted": inserted}

@app.post("/api/v1/smartsauce/store-version")
def smartsauce_store(req: StoreVersionReq, request: Request, _=Depends(auth_dependency)):
    if not require_scopes(request.state.api_key, {"smartsauce.write"}):
        raise HTTPException(status_code=403, detail="Missing scope smartsauce.write")
    if not write_limiter.allow(request.state.api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    vcfg = StoreConfig(version_dir="agent/smartsauce/plans", log_file="agent/smartsauce/logs/changes.log")
    tag, path = store_version(req.doc, vcfg)
    cfg = get_cfg(); eng = init_db(cfg['database']['path'])
    insert_event(eng, "HubAPI", "CALL", json.dumps({"route":"/smartsauce/store-version","payload":{"tag":tag}}))
    return {"version_tag": tag, "path": path}

@app.post("/api/v1/smartsauce/compare")
def smartsauce_compare(req: CompareReq, request: Request, _=Depends(auth_dependency)):
    if not require_scopes(request.state.api_key, {"kb.read"}):
        raise HTTPException(status_code=403, detail="Missing scope kb.read")
    if not read_limiter.allow(request.state.api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    import os, json
    a_path = os.path.join("agent","smartsauce","plans", f"{req.version_a}.json")
    b_path = os.path.join("agent","smartsauce","plans", f"{req.version_b}.json")
    if not (os.path.exists(a_path) and os.path.exists(b_path)):
        raise HTTPException(status_code=404, detail="Version not found")
    with open(a_path,'r') as f: a = json.load(f)
    with open(b_path,'r') as f: b = json.load(f)
    diff = compare_versions(a,b)
    report = write_report(diff, outdir=os.path.join("agent","smartsauce","reports"), period="api")
    cfg = get_cfg(); eng = init_db(cfg['database']['path'])
    insert_event(eng, "HubAPI", "CALL", json.dumps({"route":"/smartsauce/compare","payload":req.model_dump()}))
    return {"differences": diff, "report_path": report}

@app.post("/api/v1/kb/daily-summary")
def kb_daily_summary(req: DailySummaryReq, request: Request, _=Depends(auth_dependency)):
    if not require_scopes(request.state.api_key, {"kb.write"}):
        raise HTTPException(status_code=403, detail="Missing scope kb.write")
    if not write_limiter.allow(request.state.api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    from ..db.knowledge import insert_daily_summary
    cfg = get_cfg(); eng = init_db(cfg['database']['path'])
    insert_daily_summary(eng, user_summary=req.user, llm_summary=req.llm,
                         financial_summary=req.financial, automation_summary=req.automation, artifacts=req.artifacts or {})
    insert_event(eng, "HubAPI", "CALL", json.dumps({"route":"/kb/daily-summary","payload":req.model_dump()}))
    return {"status":"ok"}

@app.get("/api/v1/kb/events")
def kb_events(limit: int = 50, request: Request = None, _=Depends(auth_dependency)):
    if not require_scopes(request.state.api_key, {"kb.read"}):
        raise HTTPException(status_code=403, detail="Missing scope kb.read")
    if not read_limiter.allow(request.state.api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    cfg = get_cfg(); eng = init_db(cfg['database']['path'])
    return latest_events(eng, limit=limit)

@app.get("/api/v1/kb/summaries")
def kb_summaries(limit: int = 7, request: Request = None, _=Depends(auth_dependency)):
    if not require_scopes(request.state.api_key, {"kb.read"}):
        raise HTTPException(status_code=403, detail="Missing scope kb.read")
    if not read_limiter.allow(request.state.api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    cfg = get_cfg(); eng = init_db(cfg['database']['path'])
    return latest_summaries(eng, limit=limit)

@app.get("/api/v1/events/stream")
async def events_stream(request: Request, _=Depends(auth_dependency)):
    if not require_scopes(request.state.api_key, {"events.read"}):
        raise HTTPException(status_code=403, detail="Missing scope events.read")
    if not read_limiter.allow(request.state.api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    cfg = get_cfg(); eng = init_db(cfg['database']['path'])
    async def event_generator():
        last = None
        while True:
            rows = latest_events(eng, limit=1)
            payload = json.dumps(rows[0]) if rows else "{}"
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            await asyncio.sleep(2.0)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
