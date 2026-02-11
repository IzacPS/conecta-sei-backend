import time
from fastapi import Request
from app.core.logging import setup_logger

logger = setup_logger()


async def request_logger(request: Request, call_next):
    start = time.time()
    logger.info(f"→ {request.method} {request.url.path}")

    response = await call_next(request)

    elapsed = time.time() - start
    logger.info(
        f"← {request.method} {request.url.path} "
        f"[{response.status_code}] ({elapsed:.3f}s)"
    )

    response.headers["X-Process-Time"] = str(elapsed)
    return response
