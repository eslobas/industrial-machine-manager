from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from repositorio import RepositorioManutencao


@pytest.fixture
def client(tmp_path):
    app = create_app(RepositorioManutencao(str(tmp_path / "api.db")))
    with TestClient(app) as c:
        yield c


def criar(client, **kw):
    corpo = {"nome_maquina": "Prensa", "data_manutencao": "2026-01-01", "dias_para_proxima": 10}
    corpo.update(kw)
    return client.post("/manutencoes", json=corpo)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_criar_e_obter(client):
    r = criar(client, notas="óleo")
    assert r.status_code == 201
    m = r.json()
    assert r.headers["location"] == f"/manutencoes/{m['id']}"
    assert m["data_limite"] == "2026-01-11"
    assert m["concluida"] is False and m["data_conclusao"] is None
    assert client.get(f"/manutencoes/{m['id']}").json() == m


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("nome_maquina", ""),
        ("nome_maquina", "   "),
        ("data_manutencao", "01/01/2026"),
        ("data_manutencao", "2026-02-30"),
        ("dias_para_proxima", 0),
        ("dias_para_proxima", -1),
        ("dias_para_proxima", "dez"),
    ],
)
def test_criar_invalido_devolve_422(client, campo, valor):
    assert criar(client, **{campo: valor}).status_code == 422
    assert client.get("/manutencoes").json() == []


def test_criar_sem_campos_obrigatorios(client):
    assert client.post("/manutencoes", json={}).status_code == 422


def test_listar(client):
    criar(client, nome_maquina="A", data_manutencao="2026-01-01")
    criar(client, nome_maquina="B", data_manutencao="2026-02-01")
    assert [m["nome_maquina"] for m in client.get("/manutencoes").json()] == ["B", "A"]


def test_obter_inexistente_404(client):
    r = client.get("/manutencoes/999")
    assert r.status_code == 404
    assert "999" in r.json()["detail"]


def test_id_nao_numerico_422(client):
    assert client.get("/manutencoes/abc").status_code == 422


def test_concluir_com_corpo(client):
    mid = criar(client).json()["id"]
    r = client.post(
        f"/manutencoes/{mid}/concluir",
        json={"data_conclusao": "2026-01-05", "notas": "feito", "pecas_trocadas": "filtro"},
    )
    assert r.status_code == 200
    m = r.json()
    assert m["concluida"] is True
    assert m["data_conclusao"] == "2026-01-05"
    assert m["pecas_trocadas"] == "filtro"


def test_concluir_sem_corpo_usa_hoje(client):
    mid = criar(client).json()["id"]
    r = client.post(f"/manutencoes/{mid}/concluir")
    assert r.status_code == 200
    assert r.json()["data_conclusao"] == date.today().isoformat()


def test_concluir_duas_vezes_409(client):
    mid = criar(client).json()["id"]
    client.post(f"/manutencoes/{mid}/concluir")
    assert client.post(f"/manutencoes/{mid}/concluir").status_code == 409


def test_concluir_inexistente_404(client):
    assert client.post("/manutencoes/999/concluir").status_code == 404


def test_concluir_data_invalida_422(client):
    mid = criar(client).json()["id"]
    r = client.post(f"/manutencoes/{mid}/concluir", json={"data_conclusao": "ontem"})
    assert r.status_code == 422
    assert client.get(f"/manutencoes/{mid}").json()["concluida"] is False


def test_eliminar(client):
    mid = criar(client).json()["id"]
    r = client.delete(f"/manutencoes/{mid}")
    assert r.status_code == 204 and r.content == b""
    assert client.get(f"/manutencoes/{mid}").status_code == 404
    assert client.delete(f"/manutencoes/{mid}").status_code == 404


def test_historico(client):
    criar(client, nome_maquina="Prensa", data_manutencao="2026-02-01")
    criar(client, nome_maquina="Torno", data_manutencao="2026-01-15")
    criar(client, nome_maquina="Prensa", data_manutencao="2026-01-01")

    desc = client.get("/maquinas/Prensa/historico").json()
    assert [m["data_manutencao"] for m in desc] == ["2026-02-01", "2026-01-01"]
    asc = client.get("/maquinas/Prensa/historico", params={"ordem": "asc"}).json()
    assert [m["data_manutencao"] for m in asc] == ["2026-01-01", "2026-02-01"]
    assert client.get("/maquinas/Inexistente/historico").json() == []


def test_historico_nome_com_espacos_e_acentos(client):
    criar(client, nome_maquina="Máquina de corte 3")
    r = client.get("/maquinas/Máquina de corte 3/historico")
    assert len(r.json()) == 1


@pytest.mark.parametrize("ordem", ["DESC; DROP TABLE manutencao", "id", "random"])
def test_historico_ordem_invalida_422(client, ordem):
    criar(client)
    r = client.get("/maquinas/Prensa/historico", params={"ordem": ordem})
    assert r.status_code == 422
    assert len(client.get("/manutencoes").json()) == 1


def test_alertas(client):
    atrasada = criar(client, nome_maquina="Atrasada", data_manutencao="2026-01-01").json()  # lim 01-11
    hoje = criar(client, nome_maquina="Hoje", data_manutencao="2026-01-05").json()          # lim 01-15
    criar(client, nome_maquina="Futura", data_manutencao="2026-01-10", dias_para_proxima=30)
    feita = criar(client, nome_maquina="Feita", data_manutencao="2026-01-01").json()
    client.post(f"/manutencoes/{feita['id']}/concluir")

    r = client.get("/alertas", params={"data": "2026-01-15"}).json()
    assert [(a["id"], a["dias_atraso"]) for a in r] == [(atrasada["id"], 4), (hoje["id"], 0)]


def test_alertas_por_omissao_usa_hoje(client):
    ontem = (date.today() - timedelta(days=1)).isoformat()
    mid = criar(client, data_manutencao=ontem, dias_para_proxima=1).json()["id"]
    [a] = client.get("/alertas").json()
    assert a["id"] == mid and a["dias_atraso"] == 0


def test_alertas_data_invalida_422(client):
    assert client.get("/alertas", params={"data": "amanha"}).status_code == 422


def test_openapi_documenta_endpoints(client):
    caminhos = client.get("/openapi.json").json()["paths"]
    assert {"/manutencoes", "/manutencoes/{manutencao_id}",
            "/manutencoes/{manutencao_id}/concluir",
            "/maquinas/{nome_maquina}/historico", "/alertas"} <= set(caminhos)
