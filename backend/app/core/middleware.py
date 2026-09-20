import time
import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("indra.observability")

class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Inject request_id into request state
        request.state.request_id = request_id
        
        try:
            response = await call_next(request)
        except Exception as exc:
            process_time = (time.time() - start_time) * 1000
            log.error(f"Request {request_id} failed after {process_time:.2f}ms: {exc}")
            raise
            
        process_time = (time.time() - start_time) * 1000
        
        # Only log slow API requests or errors in production, but log all for prototype
        if request.url.path.startswith("/api/"):
            log.info(f"API {request.method} {request.url.path} [{response.status_code}] - {process_time:.2f}ms (ID: {request_id})")
            
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        return response
