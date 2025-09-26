import os, hmac, hashlib, time
from typing import Dict, Set

API_KEY = os.environ.get("HUB_API_KEY", "")
ALLOWED_IPS = set(os.environ.get("HUB_ALLOWED_IPS","").split(",")) if os.environ.get("HUB_ALLOWED_IPS") else None

def check_ip(remote_ip: str) -> bool:
    if not ALLOWED_IPS:
        return True
    return remote_ip in ALLOWED_IPS

def verify_api_key(key: str) -> bool:
    if not API_KEY:
        return False
    return hmac.compare_digest(key, API_KEY)

def verify_hmac_signature(key: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return True
    digest = hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, digest)

class RateLimiter:
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.state: Dict[str, Dict[str, float]] = {}
    def allow(self, token_id: str) -> bool:
        now = time.time()
        bucket = self.state.setdefault(token_id, {"tokens": self.capacity, "ts": now})
        elapsed = now - bucket["ts"]
        bucket["tokens"] = min(self.capacity, bucket["tokens"] + elapsed * self.refill_rate)
        bucket["ts"] = now
        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return True
        return False

read_limiter = RateLimiter(capacity=60, refill_rate_per_sec=1.0)
write_limiter = RateLimiter(capacity=10, refill_rate_per_sec=0.2)

def parse_scopes_env() -> Dict[str, Set[str]]:
    import json
    raw = os.environ.get("HUB_API_SCOPES","")
    if not raw:
        return {}
    try:
        mapping = json.loads(raw)
        return {k: set(v) for k,v in mapping.items()}
    except Exception:
        return {}

API_SCOPES_MAP = parse_scopes_env()
def require_scopes(api_key: str, needed: Set[str]) -> bool:
    if not needed:
        return True
    if API_SCOPES_MAP:
        have = API_SCOPES_MAP.get(api_key, set())
        return needed.issubset(have)
    return True
