"""Small HTTPS JSON adapter. Never exposes URLs, credentials or raw error bodies."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ApiError(Exception):
    def __init__(self, status: int | None = None, retry_after: int = 5):
        super().__init__(f"API request failed (status={status})")
        self.status = status
        self.retry_after = max(1, min(retry_after, 60))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 120) -> dict:
    request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ApiError()
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ApiError()
        return parsed
    except HTTPError as exc:
        retry = exc.headers.get("Retry-After", "5")
        status = exc.code
        exc.close()
        raise ApiError(status, int(retry) if retry.isdigit() else 5) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ApiError() from None
