"""
auditoria.py - Log de auditoria da propria aplicacao

Definição dos critérios de auditoria, para que todas as ações de auditoria sejam registradas

AAAA-MM-DD HH:MM:SS [SEVERIDADE] MODULO NOME_DO_MODULO: descricao

As acoes de auditoria sao registadas como MODULO RELATORIOS (o modulo de
relatorios e quem gera essas acoes).

Independente do core.py de proposito - nao importa nada de la, mas usa
a MESMA pasta base fixa (C:\\260462).

A pasta "Logs" so e criada na hora que alguma acao realmente acontece
(registar()) - nao e criada so por importar este modulo.
"""

import getpass
from pathlib import Path
from datetime import datetime

# Mesma pasta base fixa usada no core.py
DIRETORIO_BASE = Path(r"C:\260462")

# Mesma pasta "Logs" que os demais modulos usam (nao uma pasta separada)
PASTA_AUDITORIA = DIRETORIO_BASE / "Logs"
FICHEIRO_AUDITORIA = PASTA_AUDITORIA / "relatorios.log"

NOME_MODULO = "RELATORIOS"


def registar(acao, detalhes="", severidade="INFO"):
    """Regista uma acao no log de auditoria, no MESMO formato exigido dos
    demais modulos. Cria a pasta na hora, se ainda nao existir.

    severidade: "CRITICO", "AVISO" ou "INFO" (INFO por padrao - so usar
    CRITICO/AVISO se a propria acao de auditoria representar um problema
    real, ex: falha ao gerar um relatorio).
    """
    if not PASTA_AUDITORIA.exists():
        PASTA_AUDITORIA.mkdir(parents=True, exist_ok=True)

    utilizador = getpass.getuser()
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    descricao = acao
    if detalhes:
        descricao += f": {detalhes}"
    descricao += f" (utilizador '{utilizador}')"

    linha = f"{data_hora} [{severidade}] MODULO {NOME_MODULO}: {descricao}"

    with open(FICHEIRO_AUDITORIA, "a", encoding="utf-8") as ficheiro:
        ficheiro.write(linha + "\n")


def obter_logs():
    """Devolve todas as linhas do log de auditoria (lista vazia se ainda
    nao existir nenhuma)."""
    if not FICHEIRO_AUDITORIA.exists():
        return []

    with open(FICHEIRO_AUDITORIA, "r", encoding="utf-8") as ficheiro:
        return ficheiro.readlines()


def limpar_logs():
    """Apaga o conteudo do log de auditoria, sem apagar o arquivo em si."""
    if FICHEIRO_AUDITORIA.exists():
        open(FICHEIRO_AUDITORIA, "w", encoding="utf-8").close()
