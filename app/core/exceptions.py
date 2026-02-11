from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("conectasei")


async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"Endpoint '{request.url.path}' não encontrado",
            "path": request.url.path,
        },
    )


async def internal_error_handler(request: Request, exc):
    logger.error(f"Erro interno: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "Erro interno do servidor. Verifique os logs.",
        },
    )
