"""
auditoria.py - Log de auditoria da propria aplicacao

Diferente da pasta "Logs" (que guarda os logs de seguranca que o sistema
ANALISA), este arquivo registra as acoes de quem USA o sistema: quem
exportou o que, quando releu os logs, etc.

Independente do core.py de proposito - nao importa nada de la, mas usa
a MESMA pasta base fixa (C:\\260462) que o core.py usa pra "Logs" e
"relatorios_exportacao", pra ficar tudo junto no mesmo lugar.

A pasta "Auditoria" so e criada na hora que alguma acao realmente
acontece (registar()) - nao é criada so por importar este modulo.
"""

import getpass
from pathlib import Path
from datetime import datetime

# Mesma pasta base fixa usada no core.py
DIRETORIO_BASE = Path(r"C:\260462")

PASTA_AUDITORIA = DIRETORIO_BASE / "Auditoria"
FICHEIRO_AUDITORIA = PASTA_AUDITORIA / "auditoria.log"


def registar(acao, detalhes=""):
    """Regista uma acao no log de auditoria. Cria a pasta na hora, se
    ainda nao existir."""
    if not PASTA_AUDITORIA.exists():
        PASTA_AUDITORIA.mkdir(parents=True, exist_ok=True)

    utilizador = getpass.getuser()
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linha = f"[{data_hora}] {utilizador} | {acao}"
    if detalhes:
        linha += f" | {detalhes}"

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
