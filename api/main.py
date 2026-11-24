"""API REST sobre o repositório de manutenções.

Executar localmente:
    uvicorn api.main:app --reload

A documentação interativa fica em /docs.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse

from repositorio import (
    DadosInvalidos,
    ManutencaoJaConcluida,
    ManutencaoNaoEncontrada,
    RepositorioManutencao,
)

from .schemas import AlertaOut, Erro, ManutencaoConcluir, ManutencaoCriar, ManutencaoOut

_ERRO_404 = {404: {"model": Erro, "description": "Manutenção não encontrada"}}


def create_app(repo: Optional[RepositorioManutencao] = None) -> FastAPI:
    """Cria a aplicação. Sem ``repo``, abre a BD indicada por ``MANUTENCAO_DB``
    (ou a BD por omissão) no arranque."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.repo = repo or RepositorioManutencao()
        yield

    app = FastAPI(
        title="Industrial Machine Manager API",
        version="1.0.0",
        description="Agendamento e registo de manutenções preventivas de máquinas industriais.",
        lifespan=lifespan,
    )

    # ---------- erros do repositório -> HTTP ----------
    @app.exception_handler(ManutencaoNaoEncontrada)
    async def _nao_encontrada(_: Request, exc: ManutencaoNaoEncontrada):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ManutencaoJaConcluida)
    async def _ja_concluida(_: Request, exc: ManutencaoJaConcluida):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(DadosInvalidos)
    async def _dados_invalidos(_: Request, exc: DadosInvalidos):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    def get_repo(request: Request) -> RepositorioManutencao:
        return request.app.state.repo

    # ---------- endpoints ----------
    @app.get("/health", tags=["sistema"])
    def health():
        return {"status": "ok"}

    @app.get("/manutencoes", response_model=List[ManutencaoOut], tags=["manutenções"])
    def listar(repo: RepositorioManutencao = Depends(get_repo)):
        """Todas as manutenções, da mais recente para a mais antiga."""
        return repo.listar()

    @app.post(
        "/manutencoes",
        response_model=ManutencaoOut,
        status_code=status.HTTP_201_CREATED,
        tags=["manutenções"],
    )
    def criar(
        dados: ManutencaoCriar,
        response: Response,
        repo: RepositorioManutencao = Depends(get_repo),
    ):
        """Regista uma manutenção; a data limite é calculada automaticamente."""
        m = repo.adicionar(
            dados.nome_maquina,
            dados.data_manutencao.isoformat(),
            dados.dias_para_proxima,
            dados.notas,
            dados.pecas_trocadas,
        )
        response.headers["Location"] = f"/manutencoes/{m.id}"
        return m

    @app.get(
        "/manutencoes/{manutencao_id}",
        response_model=ManutencaoOut,
        responses=_ERRO_404,
        tags=["manutenções"],
    )
    def obter(manutencao_id: int, repo: RepositorioManutencao = Depends(get_repo)):
        return repo.obter(manutencao_id)

    @app.post(
        "/manutencoes/{manutencao_id}/concluir",
        response_model=ManutencaoOut,
        responses={**_ERRO_404, 409: {"model": Erro, "description": "Já concluída"}},
        tags=["manutenções"],
    )
    def concluir(
        manutencao_id: int,
        dados: Optional[ManutencaoConcluir] = None,
        repo: RepositorioManutencao = Depends(get_repo),
    ):
        """Marca a manutenção como concluída (sem corpo: concluída hoje, sem notas)."""
        dados = dados or ManutencaoConcluir()
        data = (dados.data_conclusao or date.today()).isoformat()
        return repo.concluir(manutencao_id, data, dados.notas, dados.pecas_trocadas)

    @app.delete(
        "/manutencoes/{manutencao_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses=_ERRO_404,
        tags=["manutenções"],
    )
    def eliminar(manutencao_id: int, repo: RepositorioManutencao = Depends(get_repo)):
        repo.eliminar(manutencao_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get(
        "/maquinas/{nome_maquina}/historico",
        response_model=List[ManutencaoOut],
        tags=["máquinas"],
    )
    def historico(
        nome_maquina: str,
        ordem: Literal["asc", "desc"] = Query("desc", description="Ordenação por data"),
        repo: RepositorioManutencao = Depends(get_repo),
    ):
        """Histórico de manutenções de uma máquina (lista vazia se não existir)."""
        return repo.historico_maquina(nome_maquina, ordem)

    @app.get("/alertas", response_model=List[AlertaOut], tags=["alertas"])
    def alertas(
        data: Optional[date] = Query(None, description="Data de referência (por omissão, hoje)"),
        repo: RepositorioManutencao = Depends(get_repo),
    ):
        """Manutenções por concluir que vencem até à data de referência, mais atrasadas primeiro."""
        referencia = data or date.today()
        return [
            AlertaOut(
                **ManutencaoOut.model_validate(m).model_dump(),
                dias_atraso=(referencia - date.fromisoformat(m.data_limite)).days,
            )
            for m in repo.pendentes_ate(referencia.isoformat())
        ]

    return app


app = create_app()
