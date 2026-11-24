from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from scripts.gerar_dados_demo import gerar

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


@pytest.fixture
def demo_db(tmp_path, monkeypatch):
    caminho = str(tmp_path / "demo.db")
    gerar(caminho, date(2025, 1, 6), date(2026, 11, 24))
    monkeypatch.setenv("MANUTENCAO_DB", caminho)
    return caminho


def test_dashboard_renderiza_com_dados(demo_db):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    rotulos = [m.label for m in at.metric]
    assert rotulos == ["Máquinas", "Pendentes", "Vencidas", "Concluídas no prazo", "Atraso médio"]
    assert at.metric[0].value == "10"
    assert any(s.value == "Vencidas" for s in at.subheader)


def test_dashboard_filtro_por_maquina(demo_db):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.multiselect[0].select("Caldeira").run()
    assert not at.exception
    assert at.metric[0].value == "1"


def test_dashboard_sem_bd(tmp_path, monkeypatch):
    monkeypatch.setenv("MANUTENCAO_DB", str(tmp_path / "nao_existe.db"))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert "Não encontrei a base de dados" in at.info[0].value
