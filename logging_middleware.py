import logging
import time
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key"}

def redact_sensitive_headers(headers: dict) -> dict:
    """Redacts sensitive headers from a dictionary of headers."""
    redacted_headers = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            redacted_headers[key] = "[REDACTED]"
        else:
            redacted_headers[key] = value
    return redacted_headers

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        process_time = time.time() - start_time

        # Convert headers to a standard dictionary
        headers = dict(request.headers)

        log_entry = {
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            "request": {
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": redact_sensitive_headers(headers),
                "client": request.client.host,
            },
            "response": {
                "status_code": response.status_code,
            },
            "processing_time_s": round(process_time, 4),
        }

        logging.info(json.dumps(log_entry))

        return response
