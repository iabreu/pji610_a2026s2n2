from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import autenticar_usuario
from app.schemas import DispositivoAtualizarLimites, DispositivoStatus
from app.supabase_client import get_supabase

router = APIRouter(prefix="/dispositivos", tags=["dispositivos"])


@router.get(
    "",
    response_model=list[DispositivoStatus],
    summary="Listar todos os dispositivos com status atual",
)
async def listar_dispositivos() -> list[dict]:
    supabase = get_supabase()
    resposta = (
        supabase.table("vw_dispositivos_status")
        .select("*")
        .eq("ativo", True)
        .order("nome")
        .execute()
    )
    return resposta.data or []


@router.get(
    "/{dispositivo_id}",
    response_model=DispositivoStatus,
    summary="Detalhar um dispositivo",
)
async def detalhar_dispositivo(dispositivo_id: UUID) -> dict:
    supabase = get_supabase()
    resposta = (
        supabase.table("vw_dispositivos_status")
        .select("*")
        .eq("id", str(dispositivo_id))
        .limit(1)
        .execute()
    )
    if not resposta.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispositivo não encontrado",
        )
    return resposta.data[0]


@router.patch(
    "/{dispositivo_id}/limites",
    response_model=DispositivoStatus,
    summary="Atualizar limites (thresholds) e intervalo offline",
)
async def atualizar_limites(
    dispositivo_id: UUID,
    payload: DispositivoAtualizarLimites,
    _usuario: dict = Depends(autenticar_usuario),
) -> dict:
    dados = payload.model_dump(exclude_none=True)
    if not dados:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum campo enviado para atualizar",
        )

    # Validar que min < max quando ambos são informados
    supabase = get_supabase()
    atual = (
        supabase.table("dispositivos")
        .select("temperatura_min, temperatura_max, umidade_min, umidade_max")
        .eq("id", str(dispositivo_id))
        .limit(1)
        .execute()
    )
    if not atual.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo não encontrado")

    merged = {**atual.data[0], **dados}
    if merged["temperatura_min"] >= merged["temperatura_max"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="temperatura_min deve ser menor que temperatura_max",
        )
    if merged["umidade_min"] >= merged["umidade_max"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="umidade_min deve ser menor que umidade_max",
        )
    resposta = (
        supabase.table("dispositivos")
        .update(dados)
        .eq("id", str(dispositivo_id))
        .execute()
    )
    if not resposta.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispositivo não encontrado",
        )

    # Retornar a versão da view (com status atual)
    return await detalhar_dispositivo(dispositivo_id)
