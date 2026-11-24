"""Pipeline de dados das manutenções (extract -> validate -> transform -> load).

    extrair     lê a tabela ``manutencao`` do SQLite (só leitura) para Polars
    validar     regras de qualidade de dados; devolve as linhas com problemas
    transformar agrega com DuckDB: KPIs, por máquina, por mês e vencidas
    carregar    grava cada tabela em Parquet

Uso:
    python -m analytics.pipeline --db manutencao.db --out saida/ [--hoje 2026-11-24]
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import polars as pl

from repositorio import DB_PADRAO, VARIAVEL_AMBIENTE_DB

COLUNAS_DATA = ("data_manutencao", "data_limite", "data_conclusao")


@dataclass(frozen=True)
class Resultado:
    kpis: pl.DataFrame
    por_maquina: pl.DataFrame
    mensal: pl.DataFrame
    vencidas: pl.DataFrame
    qualidade: pl.DataFrame

    def tabelas(self) -> dict[str, pl.DataFrame]:
        return {
            "kpis": self.kpis,
            "por_maquina": self.por_maquina,
            "mensal": self.mensal,
            "vencidas": self.vencidas,
            "qualidade": self.qualidade,
        }


# ---------------------------------------------------------------- extract
def extrair(db_path: str | os.PathLike) -> pl.DataFrame:
    """Lê todas as manutenções. Abre o SQLite em modo só-leitura: nunca cria
    nem altera a base de dados de produção."""
    caminho = Path(db_path)
    if not caminho.exists():
        raise FileNotFoundError(f"Base de dados não encontrada: {caminho}")
    with closing(sqlite3.connect(f"{caminho.resolve().as_uri()}?mode=ro", uri=True)) as conn:
        df = pl.read_database(
            "SELECT id, nome_maquina, data_manutencao, dias_para_proxima, data_limite, "
            "concluida, data_conclusao FROM manutencao",
            connection=conn,
            schema_overrides={
                "id": pl.Int64,
                "nome_maquina": pl.String,
                "data_manutencao": pl.String,
                "dias_para_proxima": pl.Int64,
                "data_limite": pl.String,
                "concluida": pl.Int64,
                "data_conclusao": pl.String,
            },
        )
    return df.with_columns(
        *[pl.col(c).str.to_date("%Y-%m-%d", strict=False) for c in COLUNAS_DATA],
        pl.col("concluida").cast(pl.Boolean),
    )


# ---------------------------------------------------------------- validate
def validar(df: pl.DataFrame) -> pl.DataFrame:
    """Regras de qualidade. Cada linha devolvida é (id, nome_maquina, problema)."""
    regras = {
        "data_manutencao inválida ou vazia": pl.col("data_manutencao").is_null(),
        "intervalo em dias não positivo": pl.col("dias_para_proxima") <= 0,
        "data_limite não bate com data + intervalo": (
            pl.col("data_limite")
            != pl.col("data_manutencao") + pl.duration(days=pl.col("dias_para_proxima"))
        ),
        "concluída sem data de conclusão": pl.col("concluida") & pl.col("data_conclusao").is_null(),
        "data de conclusão sem estar concluída": ~pl.col("concluida")
        & pl.col("data_conclusao").is_not_null(),
        "concluída antes da própria manutenção": (
            pl.col("data_conclusao") < pl.col("data_manutencao")
        ),
    }
    partes = [
        df.filter(cond.fill_null(False))
        .select("id", "nome_maquina")
        .with_columns(pl.lit(nome).alias("problema"))
        for nome, cond in regras.items()
    ]
    return pl.concat(partes).sort("id", "problema")


# ---------------------------------------------------------------- transform
_SQL_KPIS = """
SELECT
    count(*)                                                    AS registos,
    count(DISTINCT nome_maquina)                                AS maquinas,
    count(*) FILTER (WHERE concluida)                           AS concluidas,
    count(*) FILTER (WHERE NOT concluida)                       AS pendentes,
    count(*) FILTER (WHERE NOT concluida AND data_limite <= $hoje) AS vencidas,
    round(100.0 * count(*) FILTER (WHERE concluida AND data_conclusao <= data_limite)
          / nullif(count(*) FILTER (WHERE concluida), 0), 1)    AS taxa_no_prazo_pct,
    round(avg(data_conclusao - data_limite)
          FILTER (WHERE concluida AND data_conclusao > data_limite), 1) AS atraso_medio_dias
FROM base
"""

_SQL_POR_MAQUINA = """
SELECT
    nome_maquina                                                AS maquina,
    count(*)                                                    AS intervencoes,
    count(*) FILTER (WHERE concluida)                           AS concluidas,
    count(*) FILTER (WHERE NOT concluida AND data_limite <= $hoje) AS vencidas,
    round(100.0 * count(*) FILTER (WHERE concluida AND data_conclusao <= data_limite)
          / nullif(count(*) FILTER (WHERE concluida), 0), 1)    AS taxa_no_prazo_pct,
    round(avg(dias_para_proxima), 0)::int                       AS intervalo_medio_dias,
    max(data_manutencao)                                        AS ultima_manutencao,
    min(data_limite) FILTER (WHERE NOT concluida)               AS proxima_data_limite
FROM base
GROUP BY nome_maquina
ORDER BY vencidas DESC, taxa_no_prazo_pct ASC NULLS LAST, maquina
"""

_SQL_MENSAL = """
SELECT
    date_trunc('month', data_conclusao)::date                   AS mes,
    count(*)                                                    AS concluidas,
    count(*) FILTER (WHERE data_conclusao <= data_limite)       AS no_prazo,
    round(100.0 * count(*) FILTER (WHERE data_conclusao <= data_limite) / count(*), 1)
                                                                AS taxa_no_prazo_pct
FROM base
WHERE concluida AND data_conclusao IS NOT NULL
GROUP BY ALL
ORDER BY mes
"""

_SQL_VENCIDAS = """
SELECT
    id,
    nome_maquina                                                AS maquina,
    data_manutencao,
    data_limite,
    ($hoje - data_limite)::int                                  AS dias_atraso
FROM base
WHERE NOT concluida AND data_limite <= $hoje
ORDER BY dias_atraso DESC, id
"""


def transformar(df: pl.DataFrame, hoje: date | None = None) -> Resultado:
    """Agrega com DuckDB sobre o DataFrame Polars (sem cópia para uma BD).
    As linhas com problemas de qualidade ficam de fora das agregações."""
    hoje = hoje or date.today()
    qualidade = validar(df)
    base = df.filter(~pl.col("id").is_in(qualidade["id"].implode()))

    con = duckdb.connect()
    try:
        con.register("base", base)
        p = {"hoje": hoje}
        return Resultado(
            kpis=con.sql(_SQL_KPIS, params=p).pl(),
            por_maquina=con.sql(_SQL_POR_MAQUINA, params=p).pl(),
            mensal=con.sql(_SQL_MENSAL).pl(),
            vencidas=con.sql(_SQL_VENCIDAS, params=p).pl(),
            qualidade=qualidade,
        )
    finally:
        con.close()


# ---------------------------------------------------------------- load
def carregar(resultado: Resultado, destino: str | os.PathLike) -> list[Path]:
    pasta = Path(destino)
    pasta.mkdir(parents=True, exist_ok=True)
    escritos = []
    for nome, tabela in resultado.tabelas().items():
        caminho = pasta / f"{nome}.parquet"
        tabela.write_parquet(caminho)
        escritos.append(caminho)
    return escritos


def executar(db_path: str | os.PathLike, destino: str | os.PathLike | None = None,
             hoje: date | None = None) -> Resultado:
    resultado = transformar(extrair(db_path), hoje)
    if destino is not None:
        carregar(resultado, destino)
    return resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=os.environ.get(VARIAVEL_AMBIENTE_DB, DB_PADRAO))
    parser.add_argument("--out", default="saida", help="pasta para os ficheiros Parquet")
    parser.add_argument("--hoje", type=date.fromisoformat, default=None,
                        help="data de referência (AAAA-MM-DD); por omissão, hoje")
    args = parser.parse_args(argv)

    r = executar(args.db, args.out, args.hoje)
    k = r.kpis.row(0, named=True)
    print(f"{k['registos']} registos, {k['maquinas']} máquinas, "
          f"{k['vencidas']} vencidas, {k['taxa_no_prazo_pct']}% concluídas no prazo")
    if r.qualidade.height:
        print(f"Aviso: {r.qualidade.height} problema(s) de qualidade; registos excluídos:")
        print(r.qualidade)
    print(f"Parquet gravado em {Path(args.out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
