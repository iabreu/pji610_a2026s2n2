from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field



class LeituraCriar(BaseModel):
    temperatura: float = Field(..., ge=-50, le=100, description="Temperatura em °C")
    umidade: float = Field(..., ge=0, le=100, description="Umidade relativa em %")
    registrado_em: datetime | None = Field(
        default=None,
        description="Timestamp da leitura. Se omitido, usa NOW() do banco.",
    )

    amostras: int = Field(
        default=1, ge=1, description="Amostras válidas agregadas nesta leitura"
    )
    descartadas: int = Field(
        default=0, ge=0, description="Amostras descartadas na borda no mesmo ciclo"
    )
    desvio_temperatura: float | None = Field(
        default=None, ge=0, description="Desvio-padrão da temperatura no lote"
    )
    desvio_umidade: float | None = Field(
        default=None, ge=0, description="Desvio-padrão da umidade no lote"
    )


class Leitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dispositivo_id: UUID
    temperatura: float
    umidade: float
    amostras: int = 1
    descartadas: int = 0
    desvio_temperatura: float | None = None
    desvio_umidade: float | None = None
    registrado_em: datetime



class DispositivoStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    localizacao: str
    temperatura_min: float
    temperatura_max: float
    umidade_min: float
    umidade_max: float
    intervalo_offline_segundos: int
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime
    ultima_temperatura: float | None = None
    ultima_umidade: float | None = None
    ultima_leitura_em: datetime | None = None
    status: Literal["online", "offline"] = "offline"


class DispositivoAtualizarLimites(BaseModel):
    temperatura_min: float | None = Field(default=None, ge=-50, le=100)
    temperatura_max: float | None = Field(default=None, ge=-50, le=100)
    umidade_min: float | None = Field(default=None, ge=0, le=100)
    umidade_max: float | None = Field(default=None, ge=0, le=100)
    intervalo_offline_segundos: int | None = Field(default=None, ge=10, le=86400)



class Alerta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dispositivo_id: UUID
    leitura_id: UUID
    tipo: Literal[
        "temperatura_alta", "temperatura_baixa",
        "umidade_alta", "umidade_baixa",
    ]
    valor_medido: float
    limite: float
    registrado_em: datetime



class Estatisticas(BaseModel):
    dispositivo_id: UUID
    inicio: datetime
    fim: datetime
    total_leituras: int
    temperatura_media: float | None = None
    temperatura_min: float | None = None
    temperatura_max: float | None = None
    umidade_media: float | None = None
    umidade_min: float | None = None
    umidade_max: float | None = None
    total_alertas: int = 0



class Health(BaseModel):
    status: Literal["ok", "degraded"]
    versao: str
    timestamp: datetime
