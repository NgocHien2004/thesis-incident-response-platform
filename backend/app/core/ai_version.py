import httpx


def get_attck_version():
    from app.api.ai import AI_SERVICE_URL
    try:
        r = httpx.get(f"{AI_SERVICE_URL}/", timeout=2.0)
        return r.json().get("attck_version")
    except Exception:
        return None
