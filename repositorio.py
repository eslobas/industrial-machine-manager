"""Camada de dados das manutenções (SQLite).

Este módulo não depende de nenhuma interface (Tkinter, API, etc.): valida os
dados, lança exceções em caso de erro e devolve objetos ``Manutencao``. Quem o
usa decide como mostrar os erros ao utilizador.
"""

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

FORMATO_DATA = "%Y-%m-%d"
VARIAVEL_AMBIENTE_DB = "MANUTENCAO_DB"
DB_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manutencao.db")

_COLUNAS = (
    "id, nome_maquina, data_manutencao, dias_para_proxima, data_limite, "
    "concluida, data_conclusao, notas, pecas_trocadas"
)
_ORDENS_VALIDAS = ("ASC", "DESC")


# ========== EXCEÇÕES ==========
class ErroRepositorio(Exception):
    """Erro base da camada de dados."""


class DadosInvalidos(ErroRepositorio, ValueError):
    """Os dados recebidos não são válidos (data, intervalo, nome...)."""


class ManutencaoNaoEncontrada(ErroRepositorio, LookupError):
    """Não existe nenhuma manutenção com o id pedido."""

    def __init__(self, manutencao_id: int):
        super().__init__(f"Manutenção {manutencao_id} não encontrada.")
        self.manutencao_id = manutencao_id


class ManutencaoJaConcluida(ErroRepositorio):
    """A manutenção já tinha sido marcada como concluída."""

    def __init__(self, manutencao_id: int):
        super().__init__(f"A manutenção {manutencao_id} já foi concluída.")
        self.manutencao_id = manutencao_id


# ========== MODELO ==========
@dataclass(frozen=True)
class Manutencao:
    id: int
    nome_maquina: str
    data_manutencao: str
    dias_para_proxima: int
    data_limite: str
    concluida: bool
    data_conclusao: Optional[str]
    notas: str
    pecas_trocadas: str

    @classmethod
    def _de_linha(cls, linha: sqlite3.Row) -> "Manutencao":
        return cls(
            id=linha["id"],
            nome_maquina=linha["nome_maquina"],
            data_manutencao=linha["data_manutencao"],
            dias_para_proxima=linha["dias_para_proxima"],
            data_limite=linha["data_limite"],
            concluida=bool(linha["concluida"]),
            data_conclusao=linha["data_conclusao"],
            notas=linha["notas"] or "",
            pecas_trocadas=linha["pecas_trocadas"] or "",
        )


# ========== VALIDAÇÃO ==========
def validar_data(valor: str, campo: str = "data") -> str:
    """Garante que ``valor`` está no formato AAAA-MM-DD e devolve-o normalizado."""
    try:
        return datetime.strptime(str(valor).strip(), FORMATO_DATA).strftime(FORMATO_DATA)
    except ValueError:
        raise DadosInvalidos(f"{campo} inválida: '{valor}'. Use AAAA-MM-DD.") from None


def validar_dias(valor) -> int:
    try:
        dias = int(valor)
    except (TypeError, ValueError):
        raise DadosInvalidos("O intervalo em dias tem de ser um número inteiro.") from None
    if dias <= 0:
        raise DadosInvalidos("O intervalo em dias tem de ser positivo.")
    return dias


def calcular_data_limite(data_manutencao: str, dias: int) -> str:
    data = datetime.strptime(data_manutencao, FORMATO_DATA)
    return (data + timedelta(days=dias)).strftime(FORMATO_DATA)


# ========== REPOSITÓRIO ==========
class RepositorioManutencao:
    """Acesso à tabela ``manutencao``.

    O caminho da base de dados vem, por esta ordem, do argumento ``db_path``,
    da variável de ambiente ``MANUTENCAO_DB`` ou do ficheiro ``manutencao.db``
    ao lado deste módulo.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.environ.get(VARIAVEL_AMBIENTE_DB) or DB_PADRAO
        self.criar_tabelas()

    def _ligar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def criar_tabelas(self) -> None:
        with closing(self._ligar()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS manutencao (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome_maquina TEXT NOT NULL,
                    data_manutencao TEXT NOT NULL,
                    dias_para_proxima INTEGER NOT NULL,
                    data_limite TEXT NOT NULL,
                    concluida INTEGER DEFAULT 0,
                    data_conclusao TEXT,
                    notas TEXT,
                    pecas_trocadas TEXT
                )
                """
            )

    # ---------- escrita ----------
    def adicionar(
        self,
        nome_maquina: str,
        data_manutencao: str,
        dias_para_proxima,
        notas: str = "",
        pecas_trocadas: str = "",
    ) -> Manutencao:
        nome = (nome_maquina or "").strip()
        if not nome:
            raise DadosInvalidos("O nome da máquina é obrigatório.")
        data = validar_data(data_manutencao, "Data da manutenção")
        dias = validar_dias(dias_para_proxima)
        data_limite = calcular_data_limite(data, dias)

        with closing(self._ligar()) as conn, conn:
            cursor = conn.execute(
                """
                INSERT INTO manutencao
                (nome_maquina, data_manutencao, dias_para_proxima, data_limite,
                 concluida, notas, pecas_trocadas)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (nome, data, dias, data_limite, notas or "", pecas_trocadas or ""),
            )
            novo_id = cursor.lastrowid
        return self.obter(novo_id)

    def concluir(
        self,
        manutencao_id: int,
        data_conclusao: str,
        notas: str = "",
        pecas_trocadas: str = "",
    ) -> Manutencao:
        data = validar_data(data_conclusao, "Data de conclusão")
        atual = self.obter(manutencao_id)  # lança ManutencaoNaoEncontrada
        if atual.concluida:
            raise ManutencaoJaConcluida(manutencao_id)

        with closing(self._ligar()) as conn, conn:
            conn.execute(
                """
                UPDATE manutencao
                SET concluida = 1, data_conclusao = ?, notas = ?, pecas_trocadas = ?
                WHERE id = ?
                """,
                (data, notas or "", pecas_trocadas or "", manutencao_id),
            )
        return self.obter(manutencao_id)

    def eliminar(self, manutencao_id: int) -> None:
        with closing(self._ligar()) as conn, conn:
            cursor = conn.execute("DELETE FROM manutencao WHERE id = ?", (manutencao_id,))
            if cursor.rowcount == 0:
                raise ManutencaoNaoEncontrada(manutencao_id)

    # ---------- leitura ----------
    def obter(self, manutencao_id: int) -> Manutencao:
        with closing(self._ligar()) as conn:
            linha = conn.execute(
                f"SELECT {_COLUNAS} FROM manutencao WHERE id = ?", (manutencao_id,)
            ).fetchone()
        if linha is None:
            raise ManutencaoNaoEncontrada(manutencao_id)
        return Manutencao._de_linha(linha)

    def listar(self) -> List[Manutencao]:
        with closing(self._ligar()) as conn:
            linhas = conn.execute(
                f"SELECT {_COLUNAS} FROM manutencao ORDER BY data_manutencao DESC, id DESC"
            ).fetchall()
        return [Manutencao._de_linha(linha) for linha in linhas]

    def historico_maquina(self, nome_maquina: str, ordem: str = "DESC") -> List[Manutencao]:
        ordem = str(ordem).upper()
        if ordem not in _ORDENS_VALIDAS:
            raise DadosInvalidos(f"Ordem inválida: '{ordem}'. Use ASC ou DESC.")
        # 'ordem' só pode ser um dos valores da lista branca acima,
        # por isso é seguro interpolá-lo no ORDER BY.
        with closing(self._ligar()) as conn:
            linhas = conn.execute(
                f"SELECT {_COLUNAS} FROM manutencao WHERE nome_maquina = ? "
                f"ORDER BY data_manutencao {ordem}, id {ordem}",
                (nome_maquina,),
            ).fetchall()
        return [Manutencao._de_linha(linha) for linha in linhas]

    def pendentes_ate(self, data_referencia: Optional[str] = None) -> List[Manutencao]:
        """Manutenções por concluir com data limite igual ou anterior a ``data_referencia``
        (por omissão, hoje), ordenadas da mais atrasada para a menos atrasada."""
        data = validar_data(data_referencia, "Data de referência") if data_referencia \
            else date.today().strftime(FORMATO_DATA)
        with closing(self._ligar()) as conn:
            linhas = conn.execute(
                f"SELECT {_COLUNAS} FROM manutencao "
                "WHERE concluida = 0 AND data_limite <= ? ORDER BY data_limite, id",
                (data,),
            ).fetchall()
        return [Manutencao._de_linha(linha) for linha in linhas]
