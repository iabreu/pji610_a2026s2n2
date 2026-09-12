from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.analise import baseline as carregar_baseline
from app.analise import detectar_anomalias
from app.schemas import AnaliseDispositivo
from app.supabase_client import get_supabase

router = APIRouter(prefix="/analise", tags=["analise"])


@router.get(
    "/{dispositivo_id}",
    response_model=AnaliseDispositivo,
    summary="Baseline e faixa do limiar dinamico de um dispositivo",
)
async def analisar_dispositivo(dispositivo_id: UUID) -> dict:
    supabase = get_supabase()
    dispositivo = (
        supabase.table("dispositivos")
        .select("id, z_limite")
        .eq("id", str(dispositivo_id))
        .limit(1)
        .execute()
        .data
    )

    if not dispositivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispositivo não encontrado",
        )

    z_limite = float(dispositivo[0]["z_limite"])

    detectar_anomalias(dispositivo_id)
    base = carregar_baseline(dispositivo_id)

    if base is None:
        return {"dispositivo_id": dispositivo_id, "z_limite": z_limite}

    margem_temp = z_limite * float(base["desvio_temperatura"])
    margem_umid = z_limite * float(base["desvio_umidade"])

    return {
        "dispositivo_id": dispositivo_id,
        "z_limite": z_limite,
        "baseline": base,
        "temperatura_limite_inferior": round(
            float(base["media_temperatura"]) - margem_temp, 2
        ),
        "temperatura_limite_superior": round(
            float(base["media_temperatura"]) + margem_temp, 2
        ),
        "umidade_limite_inferior": round(
            float(base["media_umidade"]) - margem_umid, 2
        ),
        "umidade_limite_superior": round(
            float(base["media_umidade"]) + margem_umid, 2
        ),
    }
