import sqlite3
from contextlib import closing
from datetime import date, timedelta

import pytest

from repositorio import (
    DadosInvalidos,
    ManutencaoJaConcluida,
    ManutencaoNaoEncontrada,
    RepositorioManutencao,
)


@pytest.fixture
def repo(tmp_path):
    return RepositorioManutencao(str(tmp_path / "teste.db"))


def test_adicionar_calcula_data_limite(repo):
    m = repo.adicionar("Torno CNC", "2026-01-30", 30, notas="óleo")
    assert m.id is not None
    assert m.nome_maquina == "Torno CNC"
    assert m.data_limite == "2026-03-01"
    assert m.concluida is False
    assert m.data_conclusao is None
    assert m.notas == "óleo"
    assert m.pecas_trocadas == ""


def test_adicionar_aceita_dias_em_texto_e_remove_espacos(repo):
    m = repo.adicionar("  Prensa  ", "2026-01-01", "10")
    assert m.nome_maquina == "Prensa"
    assert m.dias_para_proxima == 10


@pytest.mark.parametrize(
    "nome, data, dias",
    [
        ("", "2026-01-01", 10),
        ("   ", "2026-01-01", 10),
        ("Prensa", "01/01/2026", 10),
        ("Prensa", "2026-02-30", 10),
        ("Prensa", "2026-01-01", 0),
        ("Prensa", "2026-01-01", -5),
        ("Prensa", "2026-01-01", "abc"),
        ("Prensa", "2026-01-01", None),
    ],
)
def test_adicionar_rejeita_dados_invalidos(repo, nome, data, dias):
    with pytest.raises(DadosInvalidos):
        repo.adicionar(nome, data, dias)
    assert repo.listar() == []


def test_obter_inexistente(repo):
    with pytest.raises(ManutencaoNaoEncontrada):
        repo.obter(999)


def test_listar_ordena_por_data_desc(repo):
    repo.adicionar("A", "2026-01-01", 10)
    repo.adicionar("B", "2026-03-01", 10)
    repo.adicionar("C", "2026-02-01", 10)
    assert [m.nome_maquina for m in repo.listar()] == ["B", "C", "A"]


def test_concluir(repo):
    m = repo.adicionar("Prensa", "2026-01-01", 10)
    c = repo.concluir(m.id, "2026-01-05", "feito", "filtro")
    assert c.concluida is True
    assert c.data_conclusao == "2026-01-05"
    assert c.notas == "feito"
    assert c.pecas_trocadas == "filtro"


def test_concluir_duas_vezes(repo):
    m = repo.adicionar("Prensa", "2026-01-01", 10)
    repo.concluir(m.id, "2026-01-05")
    with pytest.raises(ManutencaoJaConcluida):
        repo.concluir(m.id, "2026-01-06")


def test_concluir_inexistente(repo):
    with pytest.raises(ManutencaoNaoEncontrada):
        repo.concluir(999, "2026-01-05")


def test_concluir_data_invalida(repo):
    m = repo.adicionar("Prensa", "2026-01-01", 10)
    with pytest.raises(DadosInvalidos):
        repo.concluir(m.id, "ontem")
    assert repo.obter(m.id).concluida is False


def test_eliminar(repo):
    m = repo.adicionar("Prensa", "2026-01-01", 10)
    repo.eliminar(m.id)
    with pytest.raises(ManutencaoNaoEncontrada):
        repo.obter(m.id)


def test_eliminar_inexistente_lanca_erro(repo):
    with pytest.raises(ManutencaoNaoEncontrada):
        repo.eliminar(999)


def test_historico_filtra_e_ordena(repo):
    repo.adicionar("Prensa", "2026-02-01", 10)
    repo.adicionar("Torno", "2026-01-15", 10)
    repo.adicionar("Prensa", "2026-01-01", 10)

    desc = repo.historico_maquina("Prensa")
    assert [m.data_manutencao for m in desc] == ["2026-02-01", "2026-01-01"]

    asc = repo.historico_maquina("Prensa", "asc")
    assert [m.data_manutencao for m in asc] == ["2026-01-01", "2026-02-01"]


@pytest.mark.parametrize("ordem", ["", "DESC; DROP TABLE manutencao", "id", "RANDOM()"])
def test_historico_rejeita_ordem_fora_da_lista_branca(repo, ordem):
    repo.adicionar("Prensa", "2026-01-01", 10)
    with pytest.raises(DadosInvalidos):
        repo.historico_maquina("Prensa", ordem)
    assert len(repo.listar()) == 1


def test_pendentes_ate(repo):
    atrasada = repo.adicionar("Atrasada", "2026-01-01", 10)       # limite 2026-01-11
    hoje = repo.adicionar("Hoje", "2026-01-10", 5)                # limite 2026-01-15
    repo.adicionar("Futura", "2026-01-10", 30)                    # limite 2026-02-09
    concluida = repo.adicionar("Concluida", "2026-01-01", 1)      # limite 2026-01-02
    repo.concluir(concluida.id, "2026-01-02")

    pendentes = repo.pendentes_ate("2026-01-15")
    assert [m.id for m in pendentes] == [atrasada.id, hoje.id]


def test_pendentes_ate_usa_hoje_por_omissao(repo):
    ontem = (date.today() - timedelta(days=1)).isoformat()
    m = repo.adicionar("Prensa", ontem, 1)  # limite = hoje
    assert [p.id for p in repo.pendentes_ate()] == [m.id]


def test_caminho_da_bd_por_variavel_de_ambiente(tmp_path, monkeypatch):
    caminho = tmp_path / "env.db"
    monkeypatch.setenv("MANUTENCAO_DB", str(caminho))
    repo = RepositorioManutencao()
    assert repo.db_path == str(caminho)
    repo.adicionar("Prensa", "2026-01-01", 10)
    assert caminho.exists()


def test_compativel_com_bd_existente(tmp_path):
    """Uma BD criada pela versão antiga (NULL em notas/peças) continua a ler-se."""
    caminho = tmp_path / "antiga.db"
    RepositorioManutencao(str(caminho))
    with closing(sqlite3.connect(caminho)) as conn, conn:
        conn.execute(
            "INSERT INTO manutencao (nome_maquina, data_manutencao, dias_para_proxima, "
            "data_limite, concluida, notas, pecas_trocadas) "
            "VALUES ('Velha', '2025-01-01', 10, '2025-01-11', 0, NULL, NULL)"
        )
    [m] = RepositorioManutencao(str(caminho)).listar()
    assert m.notas == "" and m.pecas_trocadas == ""


def test_repositorio_nao_importa_tkinter():
    import subprocess, sys
    from pathlib import Path
    codigo = (
        "import sys; sys.modules['tkinter'] = None; "
        "import repositorio; print('ok')"
    )
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parent.parent)
    assert r.returncode == 0, r.stderr
