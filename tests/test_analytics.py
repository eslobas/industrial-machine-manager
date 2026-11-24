import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from analytics.pipeline import carregar, executar, extrair, main, transformar, validar
from repositorio import RepositorioManutencao

HOJE = date(2026, 3, 1)


@pytest.fixture
def db(tmp_path):
    caminho = str(tmp_path / "an.db")
    repo = RepositorioManutencao(caminho)
    # Prensa: concluída no prazo, concluída com 5 dias de atraso, pendente vencida (limite 02-20)
    a = repo.adicionar("Prensa", "2026-01-01", 10)               # limite 01-11
    repo.concluir(a.id, "2026-01-10")                             # no prazo
    b = repo.adicionar("Prensa", "2026-01-10", 10)               # limite 01-20
    repo.concluir(b.id, "2026-01-25")                             # 5 dias atraso
    repo.adicionar("Prensa", "2026-02-10", 10)                   # limite 02-20, vencida
    # Torno: concluída no dia limite, pendente futura
    c = repo.adicionar("Torno", "2026-02-01", 7)                 # limite 02-08
    repo.concluir(c.id, "2026-02-08")                             # no prazo (no dia)
    repo.adicionar("Torno", "2026-02-25", 30)                    # limite 03-27, futura
    return caminho


def test_extrair_tipos(db):
    df = extrair(db)
    assert df.height == 5
    assert df.schema["data_manutencao"] == pl.Date
    assert df.schema["data_conclusao"] == pl.Date
    assert df.schema["concluida"] == pl.Boolean


def test_extrair_nao_cria_bd(tmp_path):
    caminho = tmp_path / "nao_existe.db"
    with pytest.raises(FileNotFoundError):
        extrair(caminho)
    assert not caminho.exists()


def test_kpis(db):
    k = transformar(extrair(db), HOJE).kpis.row(0, named=True)
    assert k == {
        "registos": 5,
        "maquinas": 2,
        "concluidas": 3,
        "pendentes": 2,
        "vencidas": 1,
        "taxa_no_prazo_pct": pytest.approx(66.7),
        "atraso_medio_dias": pytest.approx(5.0),
    }


def test_por_maquina(db):
    t = transformar(extrair(db), HOJE).por_maquina
    linhas = {r["maquina"]: r for r in t.iter_rows(named=True)}
    assert t["maquina"].to_list() == ["Prensa", "Torno"]  # vencidas primeiro
    assert linhas["Prensa"]["vencidas"] == 1
    assert linhas["Prensa"]["taxa_no_prazo_pct"] == pytest.approx(50.0)
    assert linhas["Torno"]["taxa_no_prazo_pct"] == pytest.approx(100.0)
    assert linhas["Torno"]["proxima_data_limite"] == date(2026, 3, 27)
    assert linhas["Prensa"]["ultima_manutencao"] == date(2026, 2, 10)


def test_mensal(db):
    m = transformar(extrair(db), HOJE).mensal
    assert m.select("mes", "concluidas", "no_prazo").rows() == [
        (date(2026, 1, 1), 2, 1),
        (date(2026, 2, 1), 1, 1),
    ]


def test_vencidas_inclui_o_proprio_dia(db):
    v = transformar(extrair(db), date(2026, 2, 20)).vencidas
    assert v["dias_atraso"].to_list() == [0]
    v = transformar(extrair(db), HOJE).vencidas
    assert v["dias_atraso"].to_list() == [9]


def test_qualidade_deteta_e_exclui_registos_inconsistentes(db):
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.executemany(
            "INSERT INTO manutencao (id, nome_maquina, data_manutencao, dias_para_proxima, "
            "data_limite, concluida, data_conclusao) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (100, "Má", "2026-01-01", 10, "2026-01-05", 0, None),          # limite errado
                (101, "Má", "2026-01-01", 10, "2026-01-11", 1, None),          # sem data conclusão
                (102, "Má", "2026-01-10", 10, "2026-01-20", 1, "2026-01-05"),  # antes da manutenção
                (103, "Má", "não é data", 10, "2026-01-20", 0, None),          # data inválida
            ],
        )
    df = extrair(db)
    q = validar(df)
    assert set(q["id"].to_list()) == {100, 101, 102, 103}
    assert "concluída sem data de conclusão" in q.filter(pl.col("id") == 101)["problema"].to_list()

    r = transformar(df, HOJE)
    assert r.kpis["registos"][0] == 5            # os 4 registos maus ficam de fora
    assert "Má" not in r.por_maquina["maquina"].to_list()


def test_bd_vazia(tmp_path):
    caminho = str(tmp_path / "vazia.db")
    RepositorioManutencao(caminho)
    r = transformar(extrair(caminho), HOJE)
    k = r.kpis.row(0, named=True)
    assert k["registos"] == 0 and k["taxa_no_prazo_pct"] is None
    assert r.por_maquina.is_empty() and r.mensal.is_empty() and r.vencidas.is_empty()


def test_carregar_parquet(db, tmp_path):
    destino = tmp_path / "saida"
    r = transformar(extrair(db), HOJE)
    ficheiros = carregar(r, destino)
    assert {f.name for f in ficheiros} == {
        "kpis.parquet", "por_maquina.parquet", "mensal.parquet",
        "vencidas.parquet", "qualidade.parquet",
    }
    assert pl.read_parquet(destino / "por_maquina.parquet").equals(r.por_maquina)


def test_cli(db, tmp_path, capsys):
    assert main(["--db", db, "--out", str(tmp_path / "o"), "--hoje", "2026-03-01"]) == 0
    saida = capsys.readouterr().out
    assert "5 registos, 2 máquinas, 1 vencidas" in saida
    assert (tmp_path / "o" / "kpis.parquet").exists()


def test_executar_sem_destino_nao_grava(db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    executar(db, None, HOJE)
    assert sorted(p.name for p in Path(tmp_path).iterdir()) == ["an.db"]
