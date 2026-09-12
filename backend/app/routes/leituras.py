from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.analise import detectar_anomalias
from app.auth import autenticar_dispositivo
from app.rate_limit import rate_limit_por_ip
from app.schemas import Leitura, LeituraCriar
from app.supabase_client import get_supabase

router = APIRouter(prefix="/leituras", tags=["leituras"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Leitura,
    summary="Registrar nova leitura (ESP32)",
)
async def registrar_leitura(
    payload: LeituraCriar,
    dispositivo: dict = Depends(autenticar_dispositivo),
    _: None = Depends(rate_limit_por_ip),
) -> dict:
    supabase = get_supabase()

    dados = {
        "dispositivo_id": dispositivo["id"],
        "temperatura": payload.temperatura,
        "umidade": payload.umidade,
        "amostras": payload.amostras,
        "descartadas": payload.descartadas,
        "desvio_temperatura": payload.desvio_temperatura,
        "desvio_umidade": payload.desvio_umidade,
    }

    resposta = supabase.table("leituras").insert(dados).execute()

    if not resposta.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao gravar leitura",
        )

    try:
        detectar_anomalias(dispositivo["id"])
    except Exception:
        pass

    return resposta.data[0]


@router.get(
    "",
    response_model=list[Leitura],
    summary="Listar leituras com filtros",
)
async def listar_leituras(
    dispositivo_id: UUID | None = Query(default=None, description="Filtrar por dispositivo"),
    inicio: datetime | None = Query(default=None, description="Data/hora inicial (ISO 8601)"),
    fim: datetime | None = Query(default=None, description="Data/hora final (ISO 8601)"),
    limite: int = Query(default=500, ge=1, le=5000),
) -> list[dict]:
    supabase = get_supabase()
    query = supabase.table("leituras").select("*").order("registrado_em", desc=True)

    if dispositivo_id:
        query = query.eq("dispositivo_id", str(dispositivo_id))
    if inicio:
        query = query.gte("registrado_em", inicio.isoformat())
    if fim:
        query = query.lte("registrado_em", fim.isoformat())

    query = query.limit(limite)
    resposta = query.execute()
    return resposta.data or []


@router.get(
    "/recentes",
    response_model=list[Leitura],
    summary="Leituras das últimas N horas (atalho)",
)
async def listar_leituras_recentes(
    dispositivo_id: UUID | None = Query(default=None),
    horas: int = Query(default=24, ge=1, le=720, description="Janela em horas"),
) -> list[dict]:
    inicio = datetime.now(timezone.utc) - timedelta(hours=horas)
    supabase = get_supabase()
    query = (
        supabase.table("leituras")
        .select("*")
        .gte("registrado_em", inicio.isoformat())
        .order("registrado_em", desc=True)
    )
    if dispositivo_id:
        query = query.eq("dispositivo_id", str(dispositivo_id))
    resposta = query.limit(5000).execute()
    return resposta.data or []
