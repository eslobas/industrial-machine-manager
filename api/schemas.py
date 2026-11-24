"""Modelos Pydantic de entrada e saída da API."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NomeMaquina = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ManutencaoCriar(BaseModel):
    nome_maquina: NomeMaquina
    data_manutencao: date
    dias_para_proxima: int = Field(gt=0, le=36500, description="Intervalo até à próxima manutenção")
    notas: str = ""
    pecas_trocadas: str = ""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nome_maquina": "Torno CNC 2",
                    "data_manutencao": "2026-11-24",
                    "dias_para_proxima": 90,
                    "notas": "Mudança de óleo",
                    "pecas_trocadas": "",
                }
            ]
        }
    )


class ManutencaoConcluir(BaseModel):
    data_conclusao: Optional[date] = Field(
        default=None, description="Por omissão, a data de hoje"
    )
    notas: str = ""
    pecas_trocadas: str = ""


class ManutencaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome_maquina: str
    data_manutencao: date
    dias_para_proxima: int
    data_limite: date
    concluida: bool
    data_conclusao: Optional[date]
    notas: str
    pecas_trocadas: str


class AlertaOut(ManutencaoOut):
    dias_atraso: int = Field(description="0 = vence hoje; >0 = dias em atraso")


class Erro(BaseModel):
    detail: str
