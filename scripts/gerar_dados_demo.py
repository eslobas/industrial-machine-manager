"""Gera uma base de dados de DEMONSTRAÇÃO com histórico sintético de manutenções.

Os dados são inventados (semente fixa, resultados reprodutíveis) e servem só
para experimentar o pipeline e o dashboard. Escreve através do repositório,
por isso passam pelas mesmas validações que a API e a app de desktop.

Uso:
    python -m scripts.gerar_dados_demo --db demo.db [--desde 2025-01-06] [--ate 2026-11-24]
"""

from __future__ import annotations

import argparse
import random
from datetime import date, timedelta
from pathlib import Path

from repositorio import RepositorioManutencao

# máquina -> (intervalo em dias, probabilidade de concluir no prazo, atraso máximo em dias)
MAQUINAS = {
    "Torno CNC 1": (30, 0.92, 6),
    "Torno CNC 2": (30, 0.85, 10),
    "Fresadora 5 eixos": (45, 0.80, 12),
    "Prensa hidráulica": (60, 0.70, 20),
    "Compressor de ar": (90, 0.95, 5),
    "Robot de soldadura": (30, 0.65, 15),
    "Ponte rolante": (180, 0.90, 30),
    "Linha de pintura": (60, 0.75, 18),
    "Injetora de plástico": (45, 0.88, 8),
    "Caldeira": (90, 0.97, 4),
}

# Máquinas cuja última manutenção fica por fazer depois do prazo (para haver alertas).
EM_ATRASO = {"Robot de soldadura", "Prensa hidráulica", "Linha de pintura"}

NOTAS = ["Lubrificação", "Troca de filtros", "Inspeção geral", "Calibração", "Aperto e limpeza"]


def gerar(db_path: str, desde: date, ate: date, semente: int = 42) -> int:
    if Path(db_path).exists():
        raise FileExistsError(f"{db_path} já existe; escolha outro caminho ou apague-o.")
    rnd = random.Random(semente)
    repo = RepositorioManutencao(db_path)
    total = 0
    for maquina, (intervalo, p_prazo, atraso_max) in MAQUINAS.items():
        dia = desde + timedelta(days=rnd.randint(0, intervalo - 1))
        while dia <= ate:
            m = repo.adicionar(maquina, dia.isoformat(), intervalo, rnd.choice(NOTAS))
            total += 1
            limite = date.fromisoformat(m.data_limite)
            if maquina in EM_ATRASO and ate - timedelta(days=intervalo) < limite <= ate:
                break  # ficou esquecida: pendente e já fora do prazo
            if rnd.random() < p_prazo:
                fim = limite - timedelta(days=rnd.randint(0, min(5, intervalo // 3)))
            else:
                fim = limite + timedelta(days=rnd.randint(1, atraso_max))
            if fim > ate:  # ainda por fazer à data de referência
                break
            repo.concluir(m.id, fim.isoformat(), "Concluída", "")
            dia = fim  # a próxima manutenção conta a partir da conclusão
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera dados de demonstração (sintéticos).")
    parser.add_argument("--db", default="demo.db")
    parser.add_argument("--desde", type=date.fromisoformat, default=date(2025, 1, 6))
    parser.add_argument("--ate", type=date.fromisoformat, default=date.today())
    parser.add_argument("--semente", type=int, default=42)
    args = parser.parse_args(argv)
    n = gerar(args.db, args.desde, args.ate, args.semente)
    print(f"{n} manutenções sintéticas gravadas em {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
