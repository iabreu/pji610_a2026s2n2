from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import alertas, analise, dispositivos, estatisticas, leituras
from app.schemas import Health

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API do Projeto Integrador VI — UNIVESP. "
        "Recebe leituras de temperatura e umidade dos ESP32 e atende o dashboard."
    ),
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)


@app.get("/", tags=["health"], response_model=Health)
async def root() -> Health:
    return Health(
        status="ok",
        versao=settings.app_version,
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/health", tags=["health"], response_model=Health)
async def health() -> Health:
    return Health(
        status="ok",
        versao=settings.app_version,
        timestamp=datetime.now(timezone.utc),
    )


# Routers
app.include_router(leituras.router)
app.include_router(dispositivos.router)
app.include_router(alertas.router)
app.include_router(estatisticas.router)
app.include_router(analise.router)
