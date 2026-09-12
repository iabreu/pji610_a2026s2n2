from fastapi import Header, HTTPException, status

from app.supabase_client import get_supabase


async def autenticar_usuario(
    authorization: str | None = Header(default=None),
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cabeçalho Authorization ausente",
        )

    token = authorization.split(" ", 1)[1].strip()

    try:
        resposta = get_supabase().auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada",
        )

    if resposta is None or resposta.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada",
        )

    return {"id": resposta.user.id, "email": resposta.user.email}


async def autenticar_dispositivo(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cabeçalho X-API-Key ausente",
        )

    supabase = get_supabase()
    resposta = (
        supabase.table("dispositivos")
        .select("*")
        .eq("api_key", x_api_key)
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if not resposta.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida ou dispositivo inativo",
        )

    return resposta.data[0]
