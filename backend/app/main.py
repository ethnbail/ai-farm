from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.intelligence import router as intelligence_router
from app.api.marketplace import router as marketplace_router
from app.api.routes import router
from app.api.trading import router as trading_router
from app.core.config import get_settings
from app.database.session import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    get_engine().dispose()


app = FastAPI(title="AI Farm", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Accept", "Content-Type", "Last-Event-ID"],
)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, error: SQLAlchemyError):
    # Never leak connection strings, SQL, or credentials to browser clients.
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})


app.include_router(router)
app.include_router(trading_router, prefix="/api")
app.include_router(trading_router, include_in_schema=False)
app.include_router(intelligence_router, prefix="/api")
app.include_router(intelligence_router, include_in_schema=False)
app.include_router(marketplace_router, prefix="/api")
app.include_router(marketplace_router, include_in_schema=False)


@app.middleware("http")
async def bounded_marketplace_import(request: Request, call_next):
    if request.method in {"POST", "PUT"} and request.url.path.startswith(
        ("/api/marketplace/", "/marketplace/")
    ):
        if (
            not get_settings().local_writes_enabled
            or request.headers.get("origin") not in get_settings().cors_origins
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "Marketplace writes require LOCAL_WRITES_ENABLED=true and an explicit "
                        "trusted Origin"
                    )
                },
            )
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 1_100_000:
                return JSONResponse(
                    status_code=413, content={"detail": "Import exceeds 1 MB limit"}
                )
        request._body = bytes(data)
    return await call_next(request)
