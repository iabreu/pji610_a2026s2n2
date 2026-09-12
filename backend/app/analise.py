from uuid import UUID

from app.supabase_client import get_supabase


def detectar_anomalias(dispositivo_id: UUID | str) -> int:
    resposta = get_supabase().rpc(
        "fn_detectar_anomalias",
        {"p_dispositivo_id": str(dispositivo_id)},
    ).execute()
    return int(resposta.data or 0)


def baseline(dispositivo_id: UUID | str) -> dict | None:
    resposta = (
        get_supabase()
        .table("baselines")
        .select("*")
        .eq("dispositivo_id", str(dispositivo_id))
        .limit(1)
        .execute()
    )
    return resposta.data[0] if resposta.data else None
