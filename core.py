"""
core.py - Coração do sistema
Gerencia: Estado do sistema, parsing de logs, análise de dados
"""

import re
import os
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from functools import lru_cache

# ============================================================
# CONFIGURAÇÕES DE CAMINHOS
# ============================================================

import sys

if getattr(sys, "frozen", False):
    DIRETORIO_BASE = Path(sys.executable).resolve().parent
else:
    DIRETORIO_BASE = Path(__file__).resolve().parent

PASTA_LOGS = DIRETORIO_BASE / "logs"
PASTA_RELATORIOS = DIRETORIO_BASE / "relatorios_exportacao"

PASTA_LOGS.mkdir(parents=True, exist_ok=True)
PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)


# ============================================================
# VARIÁVEIS GLOBAIS
# ============================================================

estado_sistema = None
ultima_leitura = None


# ============================================================
# CLASSE: Evento
# ============================================================


class Evento:
    """Representa um evento do sistema"""

    __slots__ = ["timestamp", "event_type", "payload"]

    def __init__(self, event_type: str, payload):
        self.timestamp = datetime.now()
        self.event_type = event_type
        self.payload = payload

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.event_type}: {self.payload}"


# ============================================================
# CLASSE: EstadoDoSistema
# ============================================================


class EstadoDoSistema:
    """Gerencia o estado do sistema e eventos"""

    def __init__(self):
        self.events = []
        self.errors = 0
        self.executions = 0
        self.eventos_por_modulo = defaultdict(list)
        self.total_eventos_lidos = 0
        self.modulos_encontrados = set()
        self.utilizadores = set()
        self._cache = {}

    def adicionar_evento(self, tipo: str, payload):
        evento = Evento(tipo, payload)
        self.events.append(evento)
        self.executions += 1
        self.total_eventos_lidos += 1
        self._cache.clear()

        if isinstance(payload, dict) and "modulo" in payload:
            modulo = payload["modulo"]
            self.eventos_por_modulo[modulo].append(evento)
            self.modulos_encontrados.add(modulo)
            if "utilizador" in payload:
                self.utilizadores.add(payload["utilizador"])
        else:
            self.eventos_por_modulo["GERAL"].append(evento)
            self.modulos_encontrados.add("GERAL")

    def contar_eventos_por_tipo(self):
        if "contagem_tipos" not in self._cache:
            contagem = {}
            for evento in self.events:
                contagem[evento.event_type] = contagem.get(evento.event_type, 0) + 1
            self._cache["contagem_tipos"] = contagem
        return self._cache["contagem_tipos"]

    def ultimos_eventos(self, n: int):
        return self.events[-n:] if self.events else []

    def registrar_erro(self):
        self.errors += 1

    def get_eventos_por_modulo(self):
        return dict(self.eventos_por_modulo)

    def get_modulos(self):
        return sorted(self.modulos_encontrados)

    def get_utilizadores(self):
        return sorted(self.utilizadores)

    def limpar_eventos(self):
        self.events = []
        self.eventos_por_modulo = defaultdict(list)
        self.modulos_encontrados = set()
        self.total_eventos_lidos = 0
        self.utilizadores = set()
        self._cache = {}


# ============================================================
# FUNÇÕES DE PARSING DE LOGS
# ============================================================


def _determinar_tipo_evento(descricao, severidade):
    desc_lower = descricao.lower()
    tipos = [
        (["desativado", "desativada"], "DESATIVACAO"),
        (["excluído", "excluido", "exclusão", "exclusao"], "EXCLUSAO"),
        (["falha", "erro"], "ERRO"),
        (["login", "sessão", "sessao"], "AUTENTICACAO"),
        (["backup", "cópia", "copia"], "BACKUP"),
        (["query"], "CONSULTA"),
        (["brute-force", "brute force"], "SEGURANCA"),
    ]
    for palavras, tipo in tipos:
        if any(palavra in desc_lower for palavra in palavras):
            return tipo
    if "critical" in severidade.lower():
        return "CRITICO"
    return "EVENTO"


def _parse_linha_log(linha):
    """Parseia uma linha de log"""
    padrao = r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s+MÓDULO\s+([^:]+):\s+(.+)"
    match = re.match(padrao, linha.strip())

    if match:
        data_str = match.group(1)
        hora_str = match.group(2)
        severidade = match.group(3)
        modulo = match.group(4).strip().upper()
        descricao = match.group(5).strip()

        user_match = re.search(
            r"utilizador\s*['\"]?([a-zA-Z0-9_]+)['\"]?", descricao, re.IGNORECASE
        )
        utilizador = user_match.group(1) if user_match else None

        severidade_map = {"CRITICAL": "CRITICAL", "WARNING": "WARNING"}
        severidade_normalizada = severidade_map.get(severidade.upper(), "INFO")
        tipo_evento = _determinar_tipo_evento(descricao, severidade)

        try:
            data_hora = datetime.strptime(f"{data_str} {hora_str}", "%Y-%m-%d %H:%M:%S")
        except:
            data_hora = datetime.now()

        payload = {
            "modulo": modulo,
            "descricao": descricao,
            "severidade": severidade_normalizada,
            "severidade_original": severidade,
            "data_original": f"{data_str} {hora_str}",
            "data_hora": data_hora.strftime("%Y-%m-%d %H:%M:%S"),
            "arquivo": "sistema_analytics.log",
        }

        if utilizador:
            payload["utilizador"] = utilizador

        return (tipo_evento, payload, data_hora)

    # Tentar formato alternativo
    padrao2 = r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s+(.+)"
    match2 = re.match(padrao2, linha.strip())

    if match2:
        data_str = match2.group(1)
        hora_str = match2.group(2)
        severidade = match2.group(3)
        resto = match2.group(4)

        modulo_match = re.search(r"MÓDULO\s+([^:]+):", resto)
        if modulo_match:
            modulo = modulo_match.group(1).strip().upper()
            descricao = resto[resto.find(":") + 1 :].strip()
        else:
            modulo = "DESCONHECIDO"
            descricao = resto

        try:
            data_hora = datetime.strptime(f"{data_str} {hora_str}", "%Y-%m-%d %H:%M:%S")
        except:
            data_hora = datetime.now()

        if severidade.upper() == "CRITICAL":
            severidade_normalizada = "CRITICAL"
        elif severidade.upper() == "WARNING":
            severidade_normalizada = "WARNING"
        else:
            severidade_normalizada = "INFO"

        payload = {
            "modulo": modulo,
            "descricao": descricao,
            "severidade": severidade_normalizada,
            "severidade_original": severidade,
            "data_hora": data_hora.strftime("%Y-%m-%d %H:%M:%S"),
        }

        return ("EVENTO", payload, data_hora)

    return None


def ler_logs_pasta(estado=None):
    """Lê todos os logs da pasta e retorna lista de eventos"""
    global estado_sistema, ultima_leitura

    if estado is None:
        estado = estado_sistema

    if estado:
        estado.limpar_eventos()

    pasta = PASTA_LOGS

    if not pasta.exists():
        print(f"[AVISO] Pasta não encontrada: {pasta}")
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            print(f"[OK] Pasta criada: {pasta}")
        except Exception as e:
            print(f"[ERRO] Nao foi possivel criar a pasta: {e}")
            return []

    arquivos = list(pasta.glob("*.log")) + list(pasta.glob("*.txt"))

    if not arquivos:
        print(f"\n[AVISO] Nenhum arquivo .log ou .txt encontrado em: {pasta}")
        return []

    eventos = []

    print(f"\nLendo logs da pasta: {pasta}")
    print("=" * 60)

    for arquivo in arquivos:
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                linhas = f.readlines()
                if linhas:
                    print(f"\n[OK] {arquivo.name}: {len(linhas)} linhas")
                    for linha in linhas:
                        linha = linha.strip()
                        if not linha:
                            continue

                        resultado = _parse_linha_log(linha)
                        if resultado and estado:
                            tipo, payload, timestamp = resultado
                            evento = Evento(tipo, payload)
                            evento.timestamp = timestamp
                            eventos.append(evento)
                            estado.adicionar_evento(tipo, payload)
                else:
                    print(f"\n[AVISO] {arquivo.name}: vazio")
        except Exception as e:
            print(f"\n[ERRO] {arquivo.name}: {e}")

    ultima_leitura = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if estado:
        estado._cache.clear()

    # Atualiza a variável global estado_sistema
    if estado is not None:
        estado_sistema = estado

    return eventos


# ============================================================
# FUNÇÃO: inicializar()
# ============================================================


def inicializar(estado=None):
    global estado_sistema

    try:
        if estado:
            estado_sistema = estado
        else:
            estado_sistema = EstadoDoSistema()

        if PASTA_LOGS.exists():
            print("\nCaminhos e arquivos:")
            arquivos = list(PASTA_LOGS.glob("*.log")) + list(PASTA_LOGS.glob("*.txt"))
            if arquivos:
                print(f"\n[OK] Arquivos encontrados: {len(arquivos)}")
        else:
            PASTA_LOGS.mkdir(parents=True, exist_ok=True)
            print(f"[OK] Pasta criada: {PASTA_LOGS}")

        return True

    except Exception as e:
        print(f"[ERRO] {e}")
        return False


# ============================================================
# FUNÇÃO: consultar_sistema() - ATUALIZADA COM 10 ÚLTIMOS EVENTOS
# ============================================================


def consultar_sistema():
    """Exibe consulta do sistema no console com os 10 últimos eventos"""
    global estado_sistema, ultima_leitura

    try:
        if not estado_sistema:
            print("[ERRO] Estado do sistema nao disponivel")
            return

        print("\n" + "=" * 60)
        print("  CONSULTA DO SISTEMA DE SEGURANCA")
        print("=" * 60)
        print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Pasta de logs: {PASTA_LOGS}")
        print(f"Ultima leitura: {ultima_leitura or 'Nunca'}")
        print("-" * 60)

        print("\n[ESTATISTICAS]")
        print(f"  Eventos: {len(estado_sistema.events)}")
        print(f"  Erros: {estado_sistema.errors}")
        print(f"  Execucoes: {estado_sistema.executions}")

        print("\n[MODULOS ENCONTRADOS]")
        modulos = estado_sistema.get_modulos()
        if modulos:
            for i, mod in enumerate(modulos, 1):
                qtd = len(estado_sistema.eventos_por_modulo[mod])
                print(f"  {i:2}. {mod}: {qtd} eventos")
        else:
            print("  Nenhum modulo identificado")

        # ============================================================
        # SUBSTITUÍDO: [UTILIZADORES] → [ULTIMOS 10 EVENTOS]
        # ============================================================
        print("\n[ULTIMOS 10 EVENTOS]")
        ultimos = estado_sistema.ultimos_eventos(10)
        if ultimos:
            # Cabeçalho da tabela
            print("  " + "-" * 80)
            print(
                f"  {'Data/Hora':<20} | {'Tipo':<12} | {'Modulo':<15} | {'Severidade':<10} | {'Utilizador':<15} | {'Descricao':<30}"
            )
            print("  " + "-" * 80)
            # Lista os eventos do mais antigo para o mais recente
            for evento in reversed(ultimos):
                hora = evento.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                tipo = evento.event_type if hasattr(evento, "event_type") else "EVENTO"
                modulo = ""
                descricao = ""
                severidade = ""
                utilizador = ""
                if isinstance(evento.payload, dict):
                    modulo = evento.payload.get("modulo", "")[:15]
                    descricao = evento.payload.get("descricao", "")[:30]
                    severidade = evento.payload.get("severidade", "")
                    utilizador = evento.payload.get("utilizador", "")[:15]
                print(
                    f"  {hora:<20} | {tipo:<12} | {modulo:<15} | {severidade:<10} | {utilizador:<15} | {descricao}"
                )
            print("  " + "-" * 80)
            print(f"  Total de eventos exibidos: {len(ultimos)}")
        else:
            print("  Nenhum evento recente")

        print("\n[EVENTOS POR TIPO]")
        eventos_por_tipo = estado_sistema.contar_eventos_por_tipo()
        if eventos_por_tipo:
            for tipo, contagem in sorted(
                eventos_por_tipo.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"  {tipo}: {contagem}")
        else:
            print("  Nenhum evento registado")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"[ERRO] {e}")


# ============================================================
# FUNÇÃO: detalhar_eventos_por_modulo()
# ============================================================


def detalhar_eventos_por_modulo():
    """Exibe detalhamento de eventos por módulo no console (APENAS RESUMO)"""
    global estado_sistema

    try:
        if not estado_sistema:
            print("[ERRO] Estado do sistema nao disponivel")
            return

        modulos = estado_sistema.get_modulos()

        if not modulos:
            print("\n[AVISO] Nenhum modulo encontrado!")
            return

        print("\n" + "=" * 70)
        print("  DETALHE DE EVENTOS POR MODULO")
        print("=" * 70)

        total_eventos = len(estado_sistema.events)
        print(f"\nTOTAL GERAL: {total_eventos} eventos")
        print(f"MODULOS ENCONTRADOS: {len(modulos)}")

        print("\n" + "-" * 70)
        print("RESUMO POR MODULO:")
        print("-" * 70)
        print(f"{'Modulo':<25} | {'Eventos':>8} | {'%':>6} | {'Ultimo Evento':<20}")
        print("-" * 70)

        for modulo in sorted(modulos):
            eventos = estado_sistema.eventos_por_modulo[modulo]
            percentual = (
                (len(eventos) / total_eventos * 100) if total_eventos > 0 else 0
            )
            ultimo = eventos[-1] if eventos else None
            ultimo_hora = ultimo.timestamp.strftime("%H:%M:%S") if ultimo else "N/A"
            print(
                f"{modulo:<25} | {len(eventos):>8} | {percentual:>5.1f}% | {ultimo_hora:<20}"
            )

        print("-" * 70)

        for modulo in sorted(modulos):
            eventos = estado_sistema.eventos_por_modulo[modulo]

            print(f"\n{'='*70}")
            print(f"MODULO: {modulo}")
            print(f"{'='*70}")

            print(f"\nRESUMO DO MODULO {modulo}:")
            print("-" * 50)

            severidades = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
            tipos_eventos = {}
            utilizadores = set()

            for evento in eventos:
                if isinstance(evento.payload, dict):
                    sev = evento.payload.get("severidade", "INFO")
                    if sev in severidades:
                        severidades[sev] += 1

                    tipo = evento.event_type
                    tipos_eventos[tipo] = tipos_eventos.get(tipo, 0) + 1

                    if "utilizador" in evento.payload:
                        utilizadores.add(evento.payload["utilizador"])

            print(f"  Total de eventos: {len(eventos)}")
            print(f"  CRITICAL: {severidades['CRITICAL']}")
            print(f"  WARNING:  {severidades['WARNING']}")
            print(f"  INFO:     {severidades['INFO']}")

            if utilizadores:
                print(f"  Utilizadores envolvidos: {len(utilizadores)}")
                utilizadores_ordenados = sorted(utilizadores)
                colunas = 4
                largura_coluna = 22
                for i in range(0, len(utilizadores_ordenados), colunas):
                    linha_colunas = utilizadores_ordenados[i : i + colunas]
                    linha_formatada = "     " + "".join(
                        [f"{u:<{largura_coluna}}" for u in linha_colunas]
                    )
                    print(linha_formatada)
                if len(utilizadores_ordenados) > 20:
                    print(
                        f"     ... total de {len(utilizadores_ordenados)} utilizadores"
                    )
            else:
                print("  Nenhum utilizador envolvido")

            if tipos_eventos:
                print(f"\n  Tipos de evento:")
                for tipo, qtd in sorted(
                    tipos_eventos.items(), key=lambda x: x[1], reverse=True
                ):
                    print(f"     - {tipo}: {qtd}")

        print("\n" + "=" * 70)

    except Exception as e:
        print(f"[ERRO] {e}")


# ============================================================
# FUNÇÃO: gerar_relatorio_analitico()
# ============================================================


def gerar_relatorio_analitico():
    """Gera relatório analítico como string (TODOS OS DADOS)"""
    global estado_sistema, ultima_leitura

    try:
        if not estado_sistema:
            return "[ERRO] Estado do sistema nao disponivel"

        linhas = []
        linhas.append("=" * 70)
        linhas.append("  RELATORIO ANALITICO DO SISTEMA DE SEGURANCA")
        linhas.append("=" * 70)
        linhas.append(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        linhas.append(f"Pasta de logs: {PASTA_LOGS}")
        linhas.append(f"Ultima leitura: {ultima_leitura or 'Nunca'}")
        linhas.append("-" * 70)

        linhas.append("\n1. ESTATISTICAS GERAIS")
        linhas.append("-" * 40)
        linhas.append(f"   Eventos: {len(estado_sistema.events)}")
        linhas.append(f"   Erros: {estado_sistema.errors}")
        linhas.append(f"   Execucoes: {estado_sistema.executions}")

        linhas.append("\n2. MODULOS ENCONTRADOS")
        linhas.append("-" * 40)
        modulos = estado_sistema.get_modulos()
        if modulos:
            for modulo in sorted(modulos):
                qtd = len(estado_sistema.eventos_por_modulo[modulo])
                linhas.append(f"   {modulo}: {qtd} eventos")
        else:
            linhas.append("   Nenhum modulo encontrado")

        linhas.append("\n3. UTILIZADORES")
        linhas.append("-" * 40)
        utilizadores = estado_sistema.get_utilizadores()
        if utilizadores:
            for user in utilizadores:
                linhas.append(f"   - {user}")
        else:
            linhas.append("   Nenhum utilizador identificado")

        linhas.append("\n4. EVENTOS POR TIPO")
        linhas.append("-" * 40)
        eventos_por_tipo = estado_sistema.contar_eventos_por_tipo()
        if eventos_por_tipo:
            for tipo, contagem in sorted(
                eventos_por_tipo.items(), key=lambda x: x[1], reverse=True
            ):
                linhas.append(f"   {tipo}: {contagem}")
        else:
            linhas.append("   Nenhum evento registado")

        linhas.append("\n5. ULTIMOS EVENTOS")
        linhas.append("-" * 40)
        ultimos = estado_sistema.ultimos_eventos(10)
        if ultimos:
            for evento in ultimos:
                hora = evento.timestamp.strftime("%H:%M:%S")
                modulo = ""
                descricao = ""
                if isinstance(evento.payload, dict):
                    modulo = evento.payload.get("modulo", "")
                    descricao = evento.payload.get("descricao", "")
                linhas.append(
                    f"   [{evento.event_type}] {hora} | {modulo} | {descricao}"
                )
        else:
            linhas.append("   Nenhum evento recente")

        linhas.append("\n" + "=" * 70)

        return "\n".join(linhas)

    except Exception as e:
        return f"[ERRO] {e}"


# ============================================================
# FUNÇÃO: debug_logs()
# ============================================================


def debug_logs():
    """Exibe debug dos logs no console"""
    global estado_sistema

    if not estado_sistema or not estado_sistema.events:
        print("[ERRO] Nenhum evento carregado")
        return

    print("\nDEBUG - Primeiros 30 eventos:")
    print("=" * 80)

    desativados = []
    excluidos = []

    for i, evento in enumerate(estado_sistema.events[:30]):
        if hasattr(evento, "payload"):
            payload = evento.payload
            desc = payload.get("descricao", "") if isinstance(payload, dict) else ""
            user = (
                payload.get("utilizador", "N/A") if isinstance(payload, dict) else "N/A"
            )
            tipo = evento.event_type
            modulo = payload.get("modulo", "") if isinstance(payload, dict) else ""
        else:
            continue

        if "desativado" in desc.lower():
            desativados.append(user)
        if "excluído" in desc.lower() or "excluido" in desc.lower():
            excluidos.append(user)

        print(f"{i+1:2}. [{tipo}] {modulo:15} | {user:25} | {desc[:60]}...")

    print("\n" + "=" * 80)
    print(f"\nUTILIZADORES DESATIVADOS ENCONTRADOS: {len(set(desativados))}")
    for user in set(desativados):
        print(f"   - {user}")

    print(f"\nUTILIZADORES EXCLUIDOS ENCONTRADOS: {len(set(excluidos))}")
    for user in set(excluidos):
        print(f"   - {user}")

    print("\n" + "=" * 80)
    print(f"Total de eventos carregados: {len(estado_sistema.events)}")
    print(f"Total de utilizadores: {len(estado_sistema.get_utilizadores())}")


# ============================================================
# FUNÇÕES DE EXTRAÇÃO DE DADOS
# ============================================================


def extrair_utilizadores_dos_eventos(eventos):
    """Extrai utilizadores dos eventos com identificação de status"""
    utilizadores = {}
    desativados = set()
    excluidos = set()
    detalhes_desativacao = {}
    detalhes_exclusao = {}

    regex_utilizador = re.compile(
        r'(?:utilizador|user|username|usuario|login)[\s\:\=\'"]+([a-zA-Z0-9_\-\.]+)',
        re.IGNORECASE,
    )
    regex_desativado = re.compile(
        r"\b(desativad[oa]|bloquead[oa]|suspens[oa]|inativad[oa]|desabilitad[oa])\b",
        re.IGNORECASE,
    )
    regex_excluido = re.compile(
        r"\b(exclu[íi]d[oa]|removid[oa]|apagad[oa]|deletad[oa]|eliminad[oa])\b",
        re.IGNORECASE,
    )
    regex_quem = re.compile(r'por\s*[\'"]?([a-zA-Z0-9_\-\.\s]+)[\'"]?', re.IGNORECASE)

    for evento in eventos:
        if not hasattr(evento, "payload") or not evento.payload:
            continue

        payload = evento.payload
        descricao = str(payload.get("descricao", ""))
        modulo = payload.get("modulo", "")
        evento_tipo = payload.get("tipo", "")

        utilizador = (
            payload.get("utilizador") or payload.get("username") or payload.get("user")
        )

        if not utilizador:
            user_match = regex_utilizador.search(descricao)
            if user_match:
                utilizador = user_match.group(1)

        if not utilizador or utilizador == "Desconhecido":
            continue

        if utilizador not in utilizadores:
            utilizadores[utilizador] = {
                "primeiro_evento": evento.timestamp,
                "ultimo_evento": evento.timestamp,
                "total_eventos": 0,
                "modulos": set(),
                "tipos_eventos": set(),
                "status": "ATIVO",
                "desativado": False,
                "excluido": False,
                "eventos_desativacao": 0,
                "eventos_exclusao": 0,
            }

        dados = utilizadores[utilizador]
        dados["total_eventos"] += 1

        if evento.timestamp < dados["primeiro_evento"]:
            dados["primeiro_evento"] = evento.timestamp
        if evento.timestamp > dados["ultimo_evento"]:
            dados["ultimo_evento"] = evento.timestamp

        if modulo:
            dados["modulos"].add(modulo)
        if evento_tipo:
            dados["tipos_eventos"].add(evento_tipo)

        descricao_lower = descricao.lower()

        if regex_desativado.search(descricao_lower):
            user_in_desc = regex_utilizador.search(descricao)
            if user_in_desc and user_in_desc.group(1).lower() == utilizador.lower():
                desativados.add(utilizador)
                dados["eventos_desativacao"] += 1
                if utilizador not in detalhes_desativacao:
                    quem_match = regex_quem.search(descricao)
                    detalhes_desativacao[utilizador] = {
                        "data_desativacao": evento.timestamp,
                        "desativado_por": (
                            quem_match.group(1) if quem_match else "Sistema"
                        ),
                        "descricao": descricao[:100],
                        "modulo": modulo,
                    }

        if regex_excluido.search(descricao_lower):
            user_in_desc = regex_utilizador.search(descricao)
            if user_in_desc and user_in_desc.group(1).lower() == utilizador.lower():
                excluidos.add(utilizador)
                dados["eventos_exclusao"] += 1
                if utilizador not in detalhes_exclusao:
                    quem_match = regex_quem.search(descricao)
                    detalhes_exclusao[utilizador] = {
                        "data_exclusao": evento.timestamp,
                        "excluido_por": (
                            quem_match.group(1) if quem_match else "Sistema"
                        ),
                        "descricao": descricao[:100],
                        "modulo": modulo,
                    }

    for user, dados in utilizadores.items():
        if user in excluidos:
            dados["status"] = "EXCLUIDO"
            dados["excluido"] = True
            if user in detalhes_exclusao:
                dados.update(detalhes_exclusao[user])
        elif user in desativados:
            dados["status"] = "DESATIVADO"
            dados["desativado"] = True
            if user in detalhes_desativacao:
                dados.update(detalhes_desativacao[user])
        else:
            dados["status"] = "ATIVO"

    return utilizadores


# ============================================================
# FUNÇÃO: extrair_estatisticas()
# ============================================================


def extrair_estatisticas(eventos):
    """Extrai estatísticas básicas dos eventos"""
    modulos = {}
    critical = 0
    warning = 0
    info = 0
    utilizadores = set()

    regex_modulo = re.compile(
        r"(AUTENTICACAO|BASE_DADOS|CAMARAS|SENSORES)", re.IGNORECASE
    )
    regex_critical = re.compile(
        r"\b(CRITICAL|CRITICO|CRIT|ERROR|ERRO)\b", re.IGNORECASE
    )
    regex_warning = re.compile(r"\b(WARNING|AVISO|WARN)\b", re.IGNORECASE)

    for evento in eventos:
        evento_str = str(evento).upper()

        mod_match = regex_modulo.search(evento_str)
        if mod_match:
            modulo = mod_match.group(1).upper()
            modulos[modulo] = modulos.get(modulo, 0) + 1

        if hasattr(evento, "payload") and isinstance(evento.payload, dict):
            user = evento.payload.get("utilizador")
            if user:
                utilizadores.add(user)

        if regex_critical.search(evento_str):
            critical += 1
        elif regex_warning.search(evento_str):
            warning += 1
        else:
            info += 1

    return {
        "modulos": modulos,
        "utilizadores": utilizadores,
        "critical": critical,
        "warning": warning,
        "info": info,
        "total_eventos": len(eventos),
    }
