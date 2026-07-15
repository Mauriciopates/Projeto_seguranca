import sys
import os
import re
import csv
import json
import logging
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from functools import lru_cache

# ============================================================
# IMPORTACOES PARA PDF (REPORTLAB)
# ============================================================

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
        PageBreak,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor

    REPORTLAB_DISPONIVEL = True
except ImportError as e:
    REPORTLAB_DISPONIVEL = False

# ============================================================
# IMPORTACOES PARA GRAFICOS (MATPLOTLIB)
# ============================================================

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    MATPLOTLIB_DISPONIVEL = True
except ImportError as e:
    MATPLOTLIB_DISPONIVEL = False

# ============================================================
# CONFIGURACAO DE CAMINHOS
# ============================================================

PASTA_LOGS = Path(r"C:\Users\mauri\Desktop\Projeto_seguranca\logs")
PASTA_RELATORIOS = Path(__file__).parent / "relatorios_pdf"
PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)

# ============================================================
# DEFINICAO DO ESTADO DO SISTEMA
# ============================================================


class Evento:
    __slots__ = ["timestamp", "event_type", "payload"]  # Otimiza uso de memória

    def __init__(self, event_type: str, payload):
        self.timestamp = datetime.now()
        self.event_type = event_type
        self.payload = payload

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.event_type}: {self.payload}"


class EstadoDoSistema:
    def __init__(self):
        self.events = []
        self.errors = 0
        self.executions = 0
        self.eventos_por_modulo = defaultdict(list)
        self.total_eventos_lidos = 0
        self.modulos_encontrados = set()
        self.utilizadores = set()
        self._cache = {}  # Cache para dados calculados frequentemente

    def adicionar_evento(self, tipo: str, payload):
        evento = Evento(tipo, payload)
        self.events.append(evento)
        self.executions += 1
        self.total_eventos_lidos += 1
        self._cache.clear()  # Limpa cache ao adicionar novos eventos

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
        """Contagem com cache"""
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
        self._cache = {}  # Limpa cache tambem


# ============================================================
# CONFIGURACAO DE LOGS
# ============================================================


def configurar_logging():
    if not PASTA_LOGS.exists():
        PASTA_LOGS.mkdir(parents=True, exist_ok=True)

    ficheiro_log = PASTA_LOGS / "relatorios.log"

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(message)s",
            handlers=[
                logging.FileHandler(ficheiro_log, encoding="utf-8"),
                logging.StreamHandler(),
            ],
        )


configurar_logging()

# ============================================================
# VARIAVEIS GLOBAIS
# ============================================================
estado_sistema = None
ultima_leitura = None

# ============================================================
# FUNCOES AUXILIARES OTIMIZADAS
# ============================================================


def _validar_configuracao():
    """Valida as configuracoes necessarias"""
    erros = []

    if not PASTA_LOGS.exists():
        erros.append(f"Pasta de logs nao encontrada: {PASTA_LOGS}")

    if not PASTA_RELATORIOS.exists():
        try:
            PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            erros.append(f"Nao foi possivel criar pasta de relatorios: {e}")

    return erros


def _determinar_tipo_evento(descricao, severidade):
    """Determina o tipo de evento baseado na descricao"""
    desc_lower = descricao.lower()

    # Palavras-chave para cada tipo (prioridade)
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


def _extrair_usuario_da_descricao(descricao):
    """Extrai nome de usuario da descricao usando regex otimizado"""
    patterns = [
        r"utilizador ['\"]([^'\"]+)['\"]",
        r"utilizador ([a-zA-Z0-9_]+)",
        r"'([a-zA-Z0-9_]+)'",
    ]
    for pattern in patterns:
        match = re.search(pattern, descricao, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extrair_quem_executou(descricao):
    """Extrai quem executou a acao (admin ou sistema)"""
    admin_match = re.search(r"por ['\"]([^'\"]+)['\"]", descricao)
    if admin_match:
        return admin_match.group(1)
    elif "admin" in descricao or "sistema" in descricao:
        return "Sistema"
    return "Desconhecido"


def _identificar_palavras_chave(descricao, palavras):
    """Verifica se alguma palavra da lista esta na descricao"""
    return any(palavra in descricao for palavra in palavras)


@lru_cache(maxsize=128)
def _extrair_dados_evento_cached(descricao, modulo, tipo):
    """Versao com cache da funcao de extracao de dados"""
    dados = {
        "tipo_autentica": "",
        "status_autentica": "",
        "local_dispositivo": "",
        "ip_origem": "",
    }

    # Extrai IP
    ip_match = re.search(r"(\d{1,3}\.){3}\d{1,3}", descricao)
    if ip_match:
        dados["ip_origem"] = ip_match.group(0)

    # Extrai nome de utilizador da descricao
    user_match = re.search(r"utilizador '([^']+)'", descricao)
    if user_match:
        dados["nome_usuario_extraido"] = user_match.group(1)

    # Analisa por modulo
    if modulo == "AUTENTICACAO":
        if "Login" in descricao:
            dados["tipo_autentica"] = "Login"
            if "sucesso" in descricao.lower():
                dados["status_autentica"] = "Sucesso"
            else:
                dados["status_autentica"] = "Falha"
        elif "Sessão" in descricao or "Sessao" in descricao:
            dados["tipo_autentica"] = "Sessao"
            if "expirada" in descricao.lower():
                dados["status_autentica"] = "Expirada"
        elif "brute-force" in descricao.lower() or "brute force" in descricao.lower():
            dados["tipo_autentica"] = "Seguranca"
            dados["status_autentica"] = "Bloqueado"
        elif "palavra-passe" in descricao.lower() or "password" in descricao.lower():
            dados["tipo_autentica"] = "Senha"
            if "falha" in descricao.lower() or "incorreta" in descricao.lower():
                dados["status_autentica"] = "Falha"
            else:
                dados["status_autentica"] = "Sucesso"

    # Local do dispositivo
    if "Câmara" in descricao or "Camera" in descricao:
        dados["local_dispositivo"] = "Camera"
        cam_match = re.search(r"Câmara[_ ]?(\d+)", descricao)
        if not cam_match:
            cam_match = re.search(r"Camera[_ ]?(\d+)", descricao)
        if cam_match:
            dados["local_dispositivo"] = f"Camera_{cam_match.group(1)}"
    elif "Sensor" in descricao:
        dados["local_dispositivo"] = "Sensor"
        sensor_match = re.search(r"Sensor[_ ]?(\w+)", descricao)
        if sensor_match:
            dados["local_dispositivo"] = f"Sensor_{sensor_match.group(1)}"
    elif "Porta" in descricao:
        dados["local_dispositivo"] = "Porta"
        porta_match = re.search(r"Porta[_ ]?(\w+)", descricao)
        if porta_match:
            dados["local_dispositivo"] = f"Porta_{porta_match.group(1)}"
    elif "DVR" in descricao:
        dados["local_dispositivo"] = "DVR"
    elif "Backup" in descricao:
        dados["local_dispositivo"] = "Backup"
    elif "Servidor" in descricao or "Servidores" in descricao:
        dados["local_dispositivo"] = "Servidor"
    elif "API" in descricao:
        dados["local_dispositivo"] = "API"
    elif "Corredor" in descricao:
        dados["local_dispositivo"] = "Corredor"
    elif "Laboratório" in descricao:
        dados["local_dispositivo"] = "Laboratorio"

    return dados


def _processar_evento_usuario(
    evento,
    utilizadores,
    desativados,
    excluidos,
    detalhes_desativacao,
    detalhes_exclusao,
):
    """Processa um evento para extrair informacoes de usuario"""
    if not isinstance(evento.payload, dict):
        return

    descricao = evento.payload.get("descricao", "").lower()
    modulo = evento.payload.get("modulo", "")
    utilizador = evento.payload.get("utilizador", "")

    if not utilizador or utilizador == "Desconhecido":
        return

    # Inicializa dados do utilizador
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
        }

    dados = utilizadores[utilizador]
    dados["total_eventos"] += 1

    if evento.timestamp < dados["primeiro_evento"]:
        dados["primeiro_evento"] = evento.timestamp
    if evento.timestamp > dados["ultimo_evento"]:
        dados["ultimo_evento"] = evento.timestamp

    if modulo:
        dados["modulos"].add(modulo)
    dados["tipos_eventos"].add(evento.event_type)

    # Verifica desativacao
    palavras_desativacao = [
        "desativado",
        "desativada",
        "bloqueio",
        "inatividade",
        "expiracao",
        "suspenso",
        "temporariamente",
        "preventivamente",
        "desactiva",
        "desabilitado",
        "inactivo",
    ]
    if _identificar_palavras_chave(descricao, palavras_desativacao):
        user = _extrair_usuario_da_descricao(descricao)
        if user:
            desativados.add(user)
            detalhes_desativacao[user] = {
                "data_desativacao": evento.timestamp,
                "desativado_por": _extrair_quem_executou(descricao),
                "descricao": evento.payload.get("descricao", ""),
                "modulo": modulo,
            }

    # Verifica exclusao
    palavras_exclusao = [
        "excluído",
        "excluida",
        "excluido",
        "exclusão",
        "exclusao",
        "delete",
        "remove",
        "eliminação",
        "eliminacao",
        "cancelamento",
        "migração",
        "limpeza",
        "apagado",
        "apagada",
    ]
    if _identificar_palavras_chave(descricao, palavras_exclusao):
        user = _extrair_usuario_da_descricao(descricao)
        if user:
            excluidos.add(user)
            detalhes_exclusao[user] = {
                "data_exclusao": evento.timestamp,
                "excluido_por": _extrair_quem_executou(descricao),
                "descricao": evento.payload.get("descricao", ""),
                "modulo": modulo,
            }


# ============================================================
# FUNCAO PARA ABRIR ARQUIVO AUTOMATICAMENTE
# ============================================================


def abrir_arquivo_automaticamente(caminho):
    """
    Tenta abrir o arquivo automaticamente no sistema operacional
    """
    try:
        if sys.platform == "win32":
            os.startfile(str(caminho))
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["open", str(caminho)])
        else:  # Linux
            subprocess.run(["xdg-open", str(caminho)])
        return True
    except Exception as e:
        print(f"   Nao foi possivel abrir automaticamente: {e}")
        return False


# ============================================================
# FUNCAO AUXILIAR: _extrair_dados_evento()
# ============================================================


def _extrair_dados_evento(descricao, modulo, tipo):
    """
    Extrai informacoes estruturadas da descricao do evento
    """
    return _extrair_dados_evento_cached(descricao, modulo, tipo)


# ============================================================
# FUNCOES DE PARSING - OTIMIZADAS
# ============================================================


def _parse_linha_log_analytics(linha):
    # Regex mais flexivel para capturar diferentes formatos
    padrao = r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s+MÓDULO\s+([^:]+):\s+(.+)"
    match = re.match(padrao, linha.strip())

    if match:
        data_str = match.group(1)
        hora_str = match.group(2)
        severidade = match.group(3)
        modulo = match.group(4).strip().upper()
        descricao = match.group(5).strip()

        # Extracao de utilizador - usar um unico padrao mais abrangente
        user_match = re.search(
            r"utilizador\s*['\"]?([a-zA-Z0-9_]+)['\"]?", descricao, re.IGNORECASE
        )
        utilizador = user_match.group(1) if user_match else None

        # Mapeamento de severidade mais eficiente
        severidade_map = {"CRITICAL": "CRITICAL", "WARNING": "WARNING"}
        severidade_normalizada = severidade_map.get(severidade.upper(), "INFO")

        # Determina tipo de evento
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

        return (tipo_evento, payload)

    return None


def _parse_linha_log_alternativo(linha):
    padrao = r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s+(.+)"
    match = re.match(padrao, linha.strip())

    if match:
        data_str = match.group(1)
        hora_str = match.group(2)
        severidade = match.group(3)
        resto = match.group(4)

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

        return ("EVENTO", payload)

    return None


# ============================================================
# FUNCAO: gerar_relatorio_utilizadores() - OTIMIZADA
# ============================================================


def _exibir_relatorio_utilizadores(utilizadores):
    """Exibe o relatorio de utilizadores formatado"""

    # Separa por status
    utilizadores_ativos = [
        (u, d) for u, d in utilizadores.items() if d["status"] == "ATIVO"
    ]
    utilizadores_desativados = [
        (u, d) for u, d in utilizadores.items() if d["status"] == "DESATIVADO"
    ]
    utilizadores_excluidos = [
        (u, d) for u, d in utilizadores.items() if d["status"] == "EXCLUIDO"
    ]

    # Ordenar por total de eventos (decrescente)
    utilizadores_ativos.sort(key=lambda x: x[1]["total_eventos"], reverse=True)
    utilizadores_desativados.sort(key=lambda x: x[1]["total_eventos"], reverse=True)
    utilizadores_excluidos.sort(key=lambda x: x[1]["total_eventos"], reverse=True)

    total_utilizadores = len(utilizadores)
    total_ativos = len(utilizadores_ativos)
    total_desativados = len(utilizadores_desativados)
    total_excluidos = len(utilizadores_excluidos)

    print(f"\nRESUMO:")
    print(f"   Total de utilizadores identificados: {total_utilizadores}")
    print(f"   Ativos: {total_ativos}")
    print(f"   Desativados: {total_desativados}")
    print(f"   Excluidos: {total_excluidos}")
    print("=" * 80)

    # ============================================================
    # UTILIZADORES ATIVOS
    # ============================================================

    print(f"\nUTILIZADORES ATIVOS ({total_ativos}):")
    print("-" * 80)

    if utilizadores_ativos:
        print(
            f"{'#':<4} | {'Utilizador':<20} | {'Eventos':>8} | {'Ultimo Evento':<20} | {'Modulos':<15}"
        )
        print("-" * 80)

        for i, (utilizador, dados) in enumerate(utilizadores_ativos[:20], 1):
            ultimo = dados["ultimo_evento"].strftime("%Y-%m-%d %H:%M")
            modulos_str = ", ".join(list(dados["modulos"])[:3])
            if len(dados["modulos"]) > 3:
                modulos_str += f" +{len(dados['modulos'])-3}"

            print(
                f"{i:<4} | {utilizador:<20} | {dados['total_eventos']:>8} | {ultimo:<20} | {modulos_str:<15}"
            )

        if len(utilizadores_ativos) > 20:
            print(f"   ... e mais {len(utilizadores_ativos)-20} utilizadores ativos")
    else:
        print("   Nenhum utilizador ativo encontrado.")

    # ============================================================
    # UTILIZADORES DESATIVADOS
    # ============================================================

    print(f"\nUTILIZADORES DESATIVADOS ({total_desativados}):")
    print("-" * 80)

    if utilizadores_desativados:
        print(
            f"{'#':<4} | {'Utilizador':<20} | {'Desativado Por':<20} | {'Data Desativacao':<20} | {'Modulo':<15}"
        )
        print("-" * 80)

        for i, (utilizador, dados) in enumerate(utilizadores_desativados, 1):
            data_desativacao = dados.get("data_desativacao", datetime.now()).strftime(
                "%Y-%m-%d %H:%M"
            )
            desativado_por = dados.get("desativado_por", "Desconhecido")
            modulo = dados.get("modulo", "N/A")

            print(
                f"{i:<4} | {utilizador:<20} | {desativado_por:<20} | {data_desativacao:<20} | {modulo:<15}"
            )
    else:
        print("   Nenhum utilizador desativado encontrado.")

    # ============================================================
    # UTILIZADORES EXCLUIDOS
    # ============================================================

    print(f"\nUTILIZADORES EXCLUIDOS ({total_excluidos}):")
    print("-" * 80)

    if utilizadores_excluidos:
        print(
            f"{'#':<4} | {'Utilizador Excluido':<20} | {'Excluido Por':<20} | {'Data Exclusao':<20} | {'Modulo':<15}"
        )
        print("-" * 80)

        for i, (utilizador, dados) in enumerate(utilizadores_excluidos, 1):
            data_exclusao = dados.get("data_exclusao", datetime.now()).strftime(
                "%Y-%m-%d %H:%M"
            )
            excluido_por = dados.get("excluido_por", "Desconhecido")
            modulo = dados.get("modulo", "N/A")

            print(
                f"{i:<4} | {utilizador:<20} | {excluido_por:<20} | {data_exclusao:<20} | {modulo:<15}"
            )
    else:
        print("   Nenhum utilizador excluido encontrado.")

    print("\n" + "=" * 80)
    print("\nLEGENDA:")
    print("   ATIVO - Utilizador que aparece nos logs (tem eventos registados)")
    print("   DESATIVADO - Identificado por evento de desativacao no log")
    print("   EXCLUIDO - Identificado por evento de exclusao no log")


def gerar_relatorio_utilizadores():
    """
    Gera um relatorio de utilizadores:
    - ATIVOS: Aparece no log (tem eventos)
    - DESATIVADOS: Identificado por eventos de desativacao no log
    - EXCLUIDOS: Identificado por eventos de exclusao no log
    """
    global estado_sistema

    if not estado_sistema or not estado_sistema.events:
        print(
            "[ERRO] Nenhum evento carregado. Execute a leitura dos logs primeiro (opcao 6)."
        )
        return

    print("\n" + "=" * 80)
    print("  RELATORIO DE UTILIZADORES - ATIVOS / DESATIVADOS / EXCLUIDOS")
    print("=" * 80)

    utilizadores = {}
    desativados = set()
    excluidos = set()
    detalhes_desativacao = {}
    detalhes_exclusao = {}

    # Processa todos os eventos
    for evento in estado_sistema.events:
        _processar_evento_usuario(
            evento,
            utilizadores,
            desativados,
            excluidos,
            detalhes_desativacao,
            detalhes_exclusao,
        )

    # Classifica utilizadores
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

    # Exibe o relatorio
    _exibir_relatorio_utilizadores(utilizadores)

    # ============================================================
    # PERGUNTAR SE DESEJA EXPORTAR PDF
    # ============================================================

    print("\nDeseja exportar este relatorio para PDF?")
    print("   [s] - Sim, exportar para PDF")
    print("   [n] - Nao, voltar ao menu")

    opcao = input("\nEscolha (s/n): ").strip().lower()

    if opcao == "s":
        # Separa novamente para exportar
        ativos = [(u, d) for u, d in utilizadores.items() if d["status"] == "ATIVO"]
        desativados_list = [
            (u, d) for u, d in utilizadores.items() if d["status"] == "DESATIVADO"
        ]
        excluidos_list = [
            (u, d) for u, d in utilizadores.items() if d["status"] == "EXCLUIDO"
        ]

        exportar_relatorio_utilizadores_pdf(ativos, desativados_list, excluidos_list)
    else:
        print("\nVoltando ao menu...")


# ============================================================
# FUNCAO: exportar_relatorio_utilizadores_pdf()
# ============================================================


def exportar_relatorio_utilizadores_pdf(
    utilizadores_ativos, utilizadores_desativados, utilizadores_excluidos
):
    """
    Exporta o relatorio de utilizadores para PDF
    """
    if not REPORTLAB_DISPONIVEL:
        print("[ERRO] ReportLab nao instalado. Execute: pip install reportlab")
        return

    if (
        not utilizadores_ativos
        and not utilizadores_desativados
        and not utilizadores_excluidos
    ):
        print("[ERRO] Nenhum dado para exportar!")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_pdf = f"relatorio_utilizadores_{timestamp}.pdf"
    caminho_pdf = PASTA_RELATORIOS / nome_pdf

    print(f"\n   A gerar PDF do relatorio de utilizadores...")

    try:
        doc = SimpleDocTemplate(  # type: ignore
            str(caminho_pdf),
            pagesize=landscape(A4),  # type: ignore
            topMargin=1.5 * cm,  # type: ignore
            bottomMargin=1.5 * cm,  # type: ignore
            leftMargin=1.5 * cm,  # type: ignore
            rightMargin=1.5 * cm,  # type: ignore
        )

        story = []
        styles = getSampleStyleSheet()  # type: ignore

        titulo_style = ParagraphStyle(  # type: ignore
            "Titulo",
            parent=styles["Heading1"],
            fontSize=18,
            alignment=1,
            spaceAfter=15,
            textColor=HexColor("#1a237e"),  # type: ignore
        )

        subtitulo_style = ParagraphStyle(  # type: ignore
            "Subtitulo",
            parent=styles["Heading2"],
            fontSize=12,
            spaceAfter=8,
            textColor=HexColor("#0d47a1"),  # type: ignore
        )

        normal_style = styles["Normal"]
        normal_style.fontSize = 9

        # CABECALHO
        story.append(Paragraph("RELATORIO DE UTILIZADORES", titulo_style))  # type: ignore
        story.append(
            Paragraph(  # type: ignore
                f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                normal_style,
            )
        )
        story.append(Spacer(1, 10))  # type: ignore

        # ============================================================
        # RESUMO
        # ============================================================
        total_ativos = len(utilizadores_ativos)
        total_desativados = len(utilizadores_desativados)
        total_excluidos = len(utilizadores_excluidos)
        total_geral = total_ativos + total_desativados + total_excluidos

        dados_resumo = [
            ["Metrica", "Quantidade"],
            ["Total de Utilizadores", str(total_geral)],
            ["Ativos", str(total_ativos)],
            ["Desativados", str(total_desativados)],
            ["Excluidos", str(total_excluidos)],
        ]

        tabela_resumo = Table(dados_resumo, colWidths=[6 * cm, 4 * cm])  # type: ignore
        tabela_resumo.setStyle(
            TableStyle(  # type: ignore
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a237e")),  # type: ignore
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),  # type: ignore
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("BACKGROUND", (0, 1), (-1, -1), HexColor("#e3f2fd")),  # type: ignore
                    ("GRID", (0, 0), (-1, -1), 1, HexColor("#1a237e")),  # type: ignore
                ]
            )
        )
        story.append(tabela_resumo)
        story.append(Spacer(1, 15))  # type: ignore

        # ============================================================
        # UTILIZADORES ATIVOS
        # ============================================================
        if utilizadores_ativos:
            story.append(Paragraph("UTILIZADORES ATIVOS", subtitulo_style))  # type: ignore
            story.append(Spacer(1, 5))  # type: ignore

            dados_ativos = [["#", "Utilizador", "Total", "Ultimo Evento", "Modulos"]]
            for i, (utilizador, dados) in enumerate(utilizadores_ativos[:50], 1):
                ultimo = dados["ultimo_evento"].strftime("%d/%m %H:%M")
                modulos_str = ", ".join(list(dados["modulos"])[:3])
                if len(dados["modulos"]) > 3:
                    modulos_str += f" +{len(dados['modulos'])-3}"

                dados_ativos.append(
                    [
                        str(i),
                        utilizador,
                        str(dados["total_eventos"]),
                        ultimo,
                        modulos_str,
                    ]
                )

            if len(utilizadores_ativos) > 50:
                dados_ativos.append(
                    [
                        "",
                        "...",
                        "",
                        "",
                        f"e mais {len(utilizadores_ativos)-50} utilizadores",
                    ]
                )

            tabela_ativos = Table(  # type: ignore
                dados_ativos,
                colWidths=[0.8 * cm, 3 * cm, 1.5 * cm, 3.5 * cm, 4 * cm],  # type: ignore
            )
            tabela_ativos.setStyle(
                TableStyle(  # type: ignore
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#2E7D32")),  # type: ignore
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),  # type: ignore
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
                        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#E8F5E9")),  # type: ignore
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),  # type: ignore
                        ("FONTSIZE", (0, 1), (-1, -1), 7),
                    ]
                )
            )
            story.append(tabela_ativos)
            story.append(Spacer(1, 15))  # type: ignore

        # ============================================================
        # UTILIZADORES DESATIVADOS
        # ============================================================
        if utilizadores_desativados:
            story.append(Paragraph("UTILIZADORES DESATIVADOS", subtitulo_style))  # type: ignore
            story.append(Spacer(1, 5))  # type: ignore

            dados_desativados = [
                ["#", "Utilizador", "Desativado Por", "Data Desativacao", "Modulo"]
            ]
            for i, (utilizador, dados) in enumerate(utilizadores_desativados, 1):
                data_desativacao = dados.get(
                    "data_desativacao", datetime.now()
                ).strftime("%d/%m/%Y %H:%M")
                desativado_por = dados.get("desativado_por", "Desconhecido")
                modulo = dados.get("modulo", "N/A")

                dados_desativados.append(
                    [str(i), utilizador, desativado_por, data_desativacao, modulo]
                )

            tabela_desativados = Table(  # type: ignore
                dados_desativados,
                colWidths=[0.8 * cm, 3 * cm, 3 * cm, 3.5 * cm, 3 * cm],  # type: ignore
            )
            tabela_desativados.setStyle(
                TableStyle(  # type: ignore
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F57F17")),  # type: ignore
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),  # type: ignore
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
                        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#FFF8E1")),  # type: ignore
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),  # type: ignore
                        ("FONTSIZE", (0, 1), (-1, -1), 7),
                    ]
                )
            )
            story.append(tabela_desativados)
            story.append(Spacer(1, 15))  # type: ignore

        # ============================================================
        # UTILIZADORES EXCLUIDOS
        # ============================================================
        if utilizadores_excluidos:
            story.append(PageBreak())  # type: ignore
            story.append(Paragraph("UTILIZADORES EXCLUIDOS", subtitulo_style))  # type: ignore
            story.append(Spacer(1, 5))  # type: ignore

            dados_excluidos = [
                ["#", "Utilizador", "Excluido Por", "Data Exclusao", "Modulo"]
            ]
            for i, (utilizador, dados) in enumerate(utilizadores_excluidos, 1):
                data_exclusao = dados.get("data_exclusao", datetime.now()).strftime(
                    "%d/%m/%Y %H:%M"
                )
                excluido_por = dados.get("excluido_por", "Desconhecido")
                modulo = dados.get("modulo", "N/A")

                dados_excluidos.append(
                    [str(i), utilizador, excluido_por, data_exclusao, modulo]
                )

            tabela_excluidos = Table(  # type: ignore
                dados_excluidos, colWidths=[0.8 * cm, 3 * cm, 3 * cm, 3.5 * cm, 3 * cm]  # type: ignore
            )
            tabela_excluidos.setStyle(
                TableStyle(  # type: ignore
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#C62828")),  # type: ignore
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),  # type: ignore
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
                        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#FFEBEE")),  # type: ignore
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),  # type: ignore
                        ("FONTSIZE", (0, 1), (-1, -1), 7),
                    ]
                )
            )
            story.append(tabela_excluidos)
            story.append(Spacer(1, 15))  # type: ignore

        # ============================================================
        # RODAPE
        # ============================================================
        story.append(Spacer(1, 20))  # type: ignore
        story.append(
            Paragraph(  # type: ignore
                f"Relatorio gerado automaticamente pelo Sistema de Seguranca | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                styles["Italic"],
            )
        )

        doc.build(story)

        print(f"\nPDF gerado com sucesso: {caminho_pdf.name}")
        print(
            f"   {total_ativos} ativos, {total_desativados} desativados, {total_excluidos} excluidos"
        )
        print(f"   Local: {caminho_pdf}")

        # Abre o PDF automaticamente
        print("\n   A abrir PDF automaticamente...")
        if abrir_arquivo_automaticamente(caminho_pdf):
            print("   PDF aberto com sucesso!")
        else:
            print(f"   O PDF esta em: {caminho_pdf}")

    except Exception as e:
        print(f"[ERRO] Erro ao gerar PDF: {e}")
        logging.error(f"Erro ao gerar PDF de utilizadores: {e}")
        import traceback

        traceback.print_exc()


# ============================================================
# FUNCAO: debug_logs() - PARA DEBUG
# ============================================================


def debug_logs():
    """
    Funcao de debug para verificar os eventos carregados
    """
    global estado_sistema

    if not estado_sistema or not estado_sistema.events:
        print("[ERRO] Nenhum evento carregado")
        return

    print("\nDEBUG - Primeiros 30 eventos:")
    print("=" * 80)

    desativados = []
    excluidos = []

    for i, evento in enumerate(estado_sistema.events[:30]):
        if isinstance(evento.payload, dict):
            desc = evento.payload.get("descricao", "")
            user = evento.payload.get("utilizador", "N/A")
            tipo = evento.event_type
            modulo = evento.payload.get("modulo", "")

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
# FUNCAO: exportar_csv_com_selecao_modulo()
# ============================================================


def exportar_csv_com_selecao_modulo():
    """
    Exporta CSV com selecao de modulo
    Colunas: ID, data_hora, status, modulo, observacao, utilizador
    """
    global estado_sistema

    if not estado_sistema or not estado_sistema.events:
        print(
            "[ERRO] Nenhum evento carregado. Execute a leitura dos logs primeiro (opcao 6)."
        )
        return None

    print("\n" + "=" * 60)
    print("  EXPORTAR CSV - SELECAO DE MODULO")
    print("=" * 60)

    modulos = estado_sistema.get_modulos()

    if not modulos:
        print("[ERRO] Nenhum modulo encontrado!")
        return None

    print("\nMODULOS DISPONIVEIS:")
    print("-" * 40)
    for i, mod in enumerate(modulos, 1):
        qtd = len(estado_sistema.eventos_por_modulo[mod])
        print(f"   {i:2}. {mod} - {qtd} eventos")
    print("-" * 40)

    print("\nExportar CSV por modulo especifico?")
    print("   [s] - Sim, escolher um modulo")
    print("   [n] - Nao, exportar todos os eventos")

    opcao = input("\nEscolha (s/n): ").strip().lower()

    modulo_selecionado = None

    if opcao == "s":
        print("\nSelecione um modulo:")
        print("   Digite o NUMERO ou o NOME do modulo")

        entrada = input("Modulo: ").strip()

        if entrada.isdigit():
            idx = int(entrada) - 1
            if 0 <= idx < len(modulos):
                modulo_selecionado = modulos[idx]
            else:
                print(f"[ERRO] Numero invalido! Use 1 a {len(modulos)}")
                return None
        else:
            entrada_upper = entrada.upper().strip()
            for mod in modulos:
                if mod.upper() == entrada_upper:
                    modulo_selecionado = mod
                    break

            if not modulo_selecionado:
                print(f"[ERRO] Modulo '{entrada}' nao encontrado!")
                print(f"   Modulos disponiveis: {', '.join(modulos)}")
                return None

        print(f"\nExportando CSV para o modulo: {modulo_selecionado}")

    elif opcao == "n":
        print("\nExportando todos os eventos...")

    else:
        print("[ERRO] Opcao invalida! Use 's' ou 'n'")
        return None

    # ============================================================
    # GERAR CSV
    # ============================================================
    return gerar_csv(modulo_selecionado)


# ============================================================
# FUNCAO: gerar_csv()
# ============================================================


def gerar_csv(modulo_selecionado=None):
    """
    Gera o CSV com as colunas: ID, data_hora, status, modulo, observacao, utilizador
    Usa virgula como separador para melhor compatibilidade
    """
    global estado_sistema

    if not estado_sistema or not estado_sistema.events:
        print("[ERRO] Nenhum evento para exportar!")
        return None

    print("\n   A gerar CSV...")

    # Filtra eventos por modulo se selecionado
    if modulo_selecionado:
        eventos = estado_sistema.eventos_por_modulo.get(modulo_selecionado, [])
        if not eventos:
            print(f"[ERRO] Nenhum evento encontrado para o modulo {modulo_selecionado}")
            return None
    else:
        eventos = estado_sistema.events

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if modulo_selecionado:
        nome_arquivo = f"csv_{modulo_selecionado}_{timestamp}.csv"
    else:
        nome_arquivo = f"csv_todos_eventos_{timestamp}.csv"

    caminho = PASTA_RELATORIOS / nome_arquivo

    # ============================================================
    # PREPARAR DADOS
    # ============================================================
    dados_exportar = []

    for idx, evento in enumerate(eventos, 1):
        if isinstance(evento.payload, dict):
            modulo = evento.payload.get("modulo", "DESCONHECIDO")
            severidade = evento.payload.get("severidade", "INFO")
            descricao = evento.payload.get("descricao", "")
            utilizador = evento.payload.get("utilizador", "")
            data_hora = evento.timestamp.strftime("%Y-%m-%d %H:%M:%S")

            # Determina o status com base na severidade
            if severidade == "CRITICAL":
                status = "CRITICO"
            elif severidade == "WARNING":
                status = "ATENCAO"
            else:
                status = "INFO"

            # Observacao e utilizador
            observacao = descricao

            # Se nao tem utilizador, coloca "Desconhecido"
            if not utilizador:
                utilizador = "Desconhecido"

            dados_exportar.append(
                {
                    "id": idx,
                    "data_hora": data_hora,
                    "status": status,
                    "modulo": modulo,
                    "observacao": observacao,
                    "utilizador": utilizador,
                }
            )

    # ============================================================
    # ESCREVER CSV - 6 COLUNAS
    # ============================================================
    try:
        with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_ALL)

            # Cabecalho com 6 colunas
            writer.writerow(
                ["ID", "Data/Hora", "Status", "Modulo", "Observacao", "Utilizador"]
            )

            # Escreve dados
            for linha in dados_exportar:
                writer.writerow(
                    [
                        linha["id"],
                        linha["data_hora"],
                        linha["status"],
                        linha["modulo"],
                        linha["observacao"],
                        linha["utilizador"],
                    ]
                )

        print(f"\nCSV gerado com sucesso: {caminho.name}")
        print(f"   {len(dados_exportar)} eventos exportados")
        print(f"   Local: {caminho}")
        print(f"   Separador: virgula (,)")
        print(f"   Colunas: ID, Data/Hora, Status, Modulo, Observacao, Utilizador")

        # Abre o CSV automaticamente
        print("\n   A abrir CSV automaticamente...")
        if abrir_arquivo_automaticamente(caminho):
            print("   CSV aberto com sucesso!")
        else:
            print(f"   O CSV esta em: {caminho}")

        return str(caminho)

    except Exception as e:
        print(f"[ERRO] Erro ao gerar CSV: {e}")
        logging.error(f"Erro ao gerar CSV: {e}")
        import traceback

        traceback.print_exc()
        return None


# ============================================================
# FUNCAO: ler_logs_pasta() - OTIMIZADA
# ============================================================


def ler_logs_pasta():
    global estado_sistema, ultima_leitura

    if estado_sistema:
        estado_sistema.limpar_eventos()

    pasta = PASTA_LOGS

    if not pasta.exists():
        print(f"[AVISO] Pasta nao encontrada: {pasta}")
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
    total_linhas = 0

    print(f"\nLendo logs da pasta: {pasta}")
    print("=" * 60)

    for arquivo in arquivos:
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                linhas = f.readlines()
                if linhas:
                    print(f"\n[OK] {arquivo.name}: {len(linhas)} linhas")
                    # Processamento em lote para melhor performance
                    for linha in linhas:
                        linha = linha.strip()
                        if not linha:
                            continue

                        evento = _parse_linha_log_analytics(linha)
                        if not evento:
                            evento = _parse_linha_log_alternativo(linha)

                        if evento and estado_sistema:
                            estado_sistema.adicionar_evento(evento[0], evento[1])
                            eventos.append(evento)
                            total_linhas += 1
                else:
                    print(f"\n[AVISO] {arquivo.name}: vazio")
        except Exception as e:
            print(f"\n[ERRO] {arquivo.name}: {e}")

    ultima_leitura = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return eventos


# ============================================================
# FUNCOES DE INICIALIZACAO
# ============================================================


def inicializar(estado=None):
    global estado_sistema

    try:
        if estado:
            estado_sistema = estado
        else:
            estado_sistema = EstadoDoSistema()
            logging.warning("Modo de teste: estado criado localmente")

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
        logging.error(f"Erro ao inicializar: {e}")
        print(f"[ERRO] {e}")
        return False


# ============================================================
# FUNCAO: consultar_sistema()
# ============================================================


def consultar_sistema():
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

        print("\n[UTILIZADORES]")
        utilizadores = estado_sistema.get_utilizadores()
        if utilizadores:
            for i, user in enumerate(utilizadores[:10], 1):
                print(f"  {i:2}. {user}")
            if len(utilizadores) > 10:
                print(f"  ... e mais {len(utilizadores)-10} utilizadores")
        else:
            print("  Nenhum utilizador identificado")

        print("\n[EVENTOS POR TIPO]")
        eventos_por_tipo = estado_sistema.contar_eventos_por_tipo()
        if eventos_por_tipo:
            for tipo, contagem in sorted(
                eventos_por_tipo.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"  {tipo}: {contagem}")
        else:
            print("  Nenhum evento registado")

        print("\n[ULTIMOS EVENTOS]")
        ultimos = estado_sistema.ultimos_eventos(5)
        if ultimos:
            for evento in ultimos:
                hora = evento.timestamp.strftime("%H:%M:%S")
                modulo = ""
                descricao = ""
                severidade = ""
                if isinstance(evento.payload, dict):
                    modulo = evento.payload.get("modulo", "")
                    descricao = evento.payload.get("descricao", "")
                    severidade = evento.payload.get("severidade", "")
                print(
                    f"  [{evento.event_type}] {hora} | {modulo} | {descricao[:50]} | {severidade}"
                )
        else:
            print("  Nenhum evento recente")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"[ERRO] {e}")
        logging.error(f"Erro em consultar_sistema: {e}")


# ============================================================
# FUNCAO: detalhar_eventos_por_modulo()
# ============================================================


def detalhar_eventos_por_modulo():
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
                print(f"     {', '.join(list(utilizadores)[:5])}")
                if len(utilizadores) > 5:
                    print(f"     ... e mais {len(utilizadores)-5} utilizadores")

            if tipos_eventos:
                print(f"  Tipos de evento mais comuns:")
                for tipo, qtd in sorted(
                    tipos_eventos.items(), key=lambda x: x[1], reverse=True
                )[:5]:
                    print(f"     - {tipo}: {qtd}")

            print(f"\nULTIMOS EVENTOS DO MODULO {modulo} (ultimos 10):")
            print("-" * 50)

            for i, evento in enumerate(eventos[-10:], 1):
                hora = evento.timestamp.strftime("%H:%M:%S")
                descricao = ""
                severidade = ""
                utilizador = ""
                if isinstance(evento.payload, dict):
                    descricao = evento.payload.get("descricao", "")
                    severidade = evento.payload.get("severidade", "")
                    utilizador = evento.payload.get("utilizador", "")

                linha = f"   {i:2}. {hora} | {evento.event_type:<12} | {descricao[:50]}"
                if utilizador:
                    linha += f" | {utilizador}"
                if severidade:
                    linha += f" | {severidade}"
                print(linha)

            if len(eventos) > 10:
                print(f"   ... e mais {len(eventos) - 10} eventos")

        print("\n" + "=" * 70)

    except Exception as e:
        print(f"[ERRO] {e}")
        logging.error(f"Erro em detalhar_eventos_por_modulo: {e}")


# ============================================================
# FUNCAO: gerar_graficos_matplotlib()
# ============================================================


def gerar_graficos_matplotlib(dados, modulo_selecionado=None):
    """
    Gera graficos usando matplotlib
    """
    if not MATPLOTLIB_DISPONIVEL:
        print("[AVISO] Matplotlib nao disponivel. Instale com: pip install matplotlib")
        return []

    pasta_temp = PASTA_RELATORIOS / "temp_graficos"
    pasta_temp.mkdir(parents=True, exist_ok=True)

    imagens = []
    cores = [
        "#FF6B6B",
        "#4ECDC4",
        "#45B7D1",
        "#96CEB4",
        "#FFEAA7",
        "#DDA0DD",
        "#FF8A5C",
        "#A29BFE",
    ]

    # ============================================================
    # 1. GRAFICO DE BARRAS - MODULOS (Top 10)
    # ============================================================
    if dados.get("modulos"):
        modulos = dados["modulos"]
        top_modulos = dict(
            sorted(modulos.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        if top_modulos:
            try:
                plt.style.use("default")  # type: ignore
                fig, ax = plt.subplots(figsize=(10, 6))  # type: ignore

                nomes = list(top_modulos.keys())
                valores = list(top_modulos.values())

                bars = ax.bar(nomes, valores, color=cores[: len(nomes)])
                ax.set_xlabel("Modulos", fontsize=12)
                ax.set_ylabel("Numero de Eventos", fontsize=12)

                titulo = "Eventos por Modulo (Top 10)"
                if modulo_selecionado:
                    titulo += f" - {modulo_selecionado}"
                ax.set_title(titulo, fontsize=14, fontweight="bold")

                for bar, val in zip(bars, valores):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.5,
                        str(val),
                        ha="center",
                        va="bottom",
                        fontsize=9,
                    )

                plt.xticks(rotation=45, ha="right")  # type: ignore
                plt.tight_layout()  # type: ignore

                caminho = pasta_temp / "grafico_modulos.png"
                plt.savefig(caminho, dpi=150, bbox_inches="tight", facecolor="white")  # type: ignore
                plt.close()  # type: ignore
                imagens.append(str(caminho))
                print("   [OK] Grafico de modulos gerado")
            except Exception as e:
                print(f"   [ERRO] Erro ao gerar grafico de modulos: {e}")

    # ============================================================
    # 2. GRAFICO DE PIZZA - SEVERIDADES
    # ============================================================
    if dados.get("severidades"):
        try:
            fig, ax = plt.subplots(figsize=(8, 8))  # type: ignore

            severidades = dados["severidades"]
            labels = list(severidades.keys())
            values = list(severidades.values())
            colors_sev = ["#FF6B6B", "#FFD93D", "#6BCB77"]

            if sum(values) > 0:
                wedges, texts, autotexts = ax.pie(
                    values,
                    labels=labels,
                    colors=colors_sev,
                    autopct="%1.1f%%",
                    shadow=True,
                    startangle=90,
                )
                ax.set_title(
                    "Distribuicao por Severidade", fontsize=14, fontweight="bold"
                )

                legenda = [
                    f"{labels[i]}: {values[i]}"
                    for i in range(len(labels))
                    if values[i] > 0
                ]
                if legenda:
                    ax.legend(legenda, loc="upper right", fontsize=10)

            plt.tight_layout()  # type: ignore
            caminho = pasta_temp / "grafico_severidades.png"
            plt.savefig(caminho, dpi=150, bbox_inches="tight", facecolor="white")  # type: ignore
            plt.close()  # type: ignore
            imagens.append(str(caminho))
            print("   [OK] Grafico de severidades gerado")
        except Exception as e:
            print(f"   [ERRO] Erro ao gerar grafico de severidades: {e}")

    # ============================================================
    # 3. GRAFICO DE TIPOS DE EVENTO (Top 5)
    # ============================================================
    if dados.get("tipos"):
        try:
            fig, ax = plt.subplots(figsize=(10, 6))  # type: ignore

            tipos = dados["tipos"]
            top_tipos = dict(
                sorted(tipos.items(), key=lambda x: x[1], reverse=True)[:5]
            )

            if top_tipos:
                nomes = list(top_tipos.keys())
                valores = list(top_tipos.values())

                bars = ax.bar(
                    nomes,
                    valores,
                    color=["#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD", "#FF8A5C"],
                )
                ax.set_xlabel("Tipo de Evento", fontsize=12)
                ax.set_ylabel("Numero de Eventos", fontsize=12)
                ax.set_title("Top 5 Tipos de Evento", fontsize=14, fontweight="bold")

                for bar, val in zip(bars, valores):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.5,
                        str(val),
                        ha="center",
                        va="bottom",
                        fontsize=10,
                    )

                plt.xticks(rotation=45, ha="right")  # type: ignore
                plt.tight_layout()  # type: ignore

                caminho = pasta_temp / "grafico_tipos.png"
                plt.savefig(caminho, dpi=150, bbox_inches="tight", facecolor="white")  # type: ignore
                plt.close()  # type: ignore
                imagens.append(str(caminho))
                print("   [OK] Grafico de tipos gerado")
        except Exception as e:
            print(f"   [ERRO] Erro ao gerar grafico de tipos: {e}")

    return imagens


# ============================================================
# FUNCAO: preparar_dados_para_graficos()
# ============================================================


def preparar_dados_para_graficos(modulo=None):
    global estado_sistema

    if not estado_sistema:
        return None

    dados = {
        "modulos": {},
        "severidades": {"CRITICAL": 0, "WARNING": 0, "INFO": 0},
        "tipos": {},
        "utilizadores": {},
    }

    if modulo:
        eventos = estado_sistema.eventos_por_modulo.get(modulo, [])
    else:
        eventos = estado_sistema.events

    if not eventos:
        return None

    for evento in eventos:
        if isinstance(evento.payload, dict):
            mod = evento.payload.get("modulo", "DESCONHECIDO")
            dados["modulos"][mod] = dados["modulos"].get(mod, 0) + 1

            sev = evento.payload.get("severidade", "INFO")
            if sev in dados["severidades"]:
                dados["severidades"][sev] += 1

            tipo = evento.event_type
            dados["tipos"][tipo] = dados["tipos"].get(tipo, 0) + 1

            user = evento.payload.get("utilizador")
            if user:
                dados["utilizadores"][user] = dados["utilizadores"].get(user, 0) + 1

    return dados


# ============================================================
# FUNCAO: gerar_pdf_relatorio()
# ============================================================


def gerar_pdf_relatorio(modulo_selecionado=None):
    global estado_sistema, ultima_leitura

    if not REPORTLAB_DISPONIVEL:
        print("[ERRO] Biblioteca 'reportlab' nao instalada.")
        print("Instale com: pip install reportlab")
        return None

    if not estado_sistema or not estado_sistema.events:
        print("[ERRO] Nenhum evento carregado. Execute a leitura dos logs primeiro.")
        return None

    print("\nA gerar relatorio PDF...")

    dados = preparar_dados_para_graficos(modulo_selecionado)

    if not dados:
        print("[ERRO] Nenhum dado disponivel para gerar graficos")
        return None

    print("   - Gerando graficos com matplotlib...")
    imagens = gerar_graficos_matplotlib(dados, modulo_selecionado)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if modulo_selecionado:
        nome_pdf = f"relatorio_{modulo_selecionado}_{timestamp}.pdf"
    else:
        nome_pdf = f"relatorio_geral_{timestamp}.pdf"
    caminho_pdf = PASTA_RELATORIOS / nome_pdf

    print("   - Criando PDF com reportlab...")

    try:
        doc = SimpleDocTemplate(  # type: ignore
            str(caminho_pdf),
            pagesize=A4,  # type: ignore
            topMargin=2 * cm,  # type: ignore
            bottomMargin=2 * cm,  # type: ignore
            leftMargin=2 * cm,  # type: ignore
            rightMargin=2 * cm,  # type: ignore
        )

        story = []
        styles = getSampleStyleSheet()  # type: ignore

        titulo_style = ParagraphStyle(  # type: ignore
            "Titulo",
            parent=styles["Heading1"],
            fontSize=20,
            alignment=1,
            spaceAfter=20,
            textColor=HexColor("#1a237e"),  # type: ignore
        )

        subtitulo_style = ParagraphStyle(  # type: ignore
            "Subtitulo",
            parent=styles["Heading2"],
            fontSize=14,
            spaceAfter=10,
            textColor=HexColor("#0d47a1"),  # type: ignore
        )

        normal_style = styles["Normal"]
        normal_style.fontSize = 10

        # CABECALHO
        story.append(Paragraph("RELATORIO ANALITICO DE SEGURANCA", titulo_style))  # type: ignore
        story.append(Spacer(1, 5))  # type: ignore

        if modulo_selecionado:
            story.append(Paragraph(f"Modulo: {modulo_selecionado}", subtitulo_style))  # type: ignore
        else:
            story.append(Paragraph("Relatorio Geral do Sistema", subtitulo_style))  # type: ignore

        story.append(
            Paragraph(  # type: ignore
                f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                normal_style,
            )
        )
        story.append(Paragraph(f"Pasta de logs: {PASTA_LOGS}", normal_style))  # type: ignore
        story.append(Spacer(1, 15))  # type: ignore

        story.append(Paragraph("-" * 80, normal_style))  # type: ignore
        story.append(Spacer(1, 10))  # type: ignore

        # RESUMO DO SISTEMA
        story.append(Paragraph("RESUMO DO SISTEMA", subtitulo_style))  # type: ignore
        story.append(Spacer(1, 5))  # type: ignore

        total_eventos = (
            len(estado_sistema.events)
            if not modulo_selecionado
            else len(estado_sistema.eventos_por_modulo.get(modulo_selecionado, []))
        )

        dados_tabela = [
            ["Metrica", "Valor"],
            ["Total de Eventos", str(total_eventos)],
            ["Modulos Encontrados", str(len(estado_sistema.get_modulos()))],
            ["Utilizadores", str(len(estado_sistema.get_utilizadores()))],
        ]

        if modulo_selecionado:
            dados_tabela.append(["Modulo Selecionado", modulo_selecionado])

        tabela = Table(dados_tabela, colWidths=[5 * cm, 5 * cm])  # type: ignore
        tabela.setStyle(
            TableStyle(  # type: ignore
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a237e")),  # type: ignore
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),  # type: ignore
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("BACKGROUND", (0, 1), (-1, -1), HexColor("#e3f2fd")),  # type: ignore
                    ("BACKGROUND", (0, 1), (-1, -1), HexColor("#e3f2fd")),  # type: ignore
                    ("GRID", (0, 0), (-1, -1), 1, HexColor("#1a237e")),  # type: ignore
                ]
            )
        )
        story.append(tabela)
        story.append(Spacer(1, 15))  # type: ignore

        # SEVERIDADES
        story.append(Paragraph("DISTRIBUICAO POR SEVERIDADE", subtitulo_style))  # type: ignore
        story.append(Spacer(1, 5))  # type: ignore

        sev = dados["severidades"]
        total_sev = sum(sev.values())
        if total_sev > 0:
            dados_sev = [
                ["Severidade", "Quantidade", "Percentual"],
                [
                    "CRITICAL",
                    str(sev["CRITICAL"]),
                    f"{sev['CRITICAL']/total_sev*100:.1f}%",
                ],
                [
                    "WARNING",
                    str(sev["WARNING"]),
                    f"{sev['WARNING']/total_sev*100:.1f}%",
                ],
                ["INFO", str(sev["INFO"]), f"{sev['INFO']/total_sev*100:.1f}%"],
            ]

            tabela_sev = Table(dados_sev, colWidths=[3 * cm, 3 * cm, 3 * cm])  # type: ignore
            tabela_sev.setStyle(
                TableStyle(  # type: ignore
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0d47a1")),  # type: ignore
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),  # type: ignore
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#e3f2fd")),  # type: ignore
                        ("GRID", (0, 0), (-1, -1), 1, HexColor("#0d47a1")),  # type: ignore
                    ]
                )
            )
            story.append(tabela_sev)
        story.append(Spacer(1, 10))  # type: ignore

        # ADICIONA IMAGENS DOS GRAFICOS
        for imagem in imagens:
            try:
                if Path(imagem).exists():
                    img = Image(imagem, width=14 * cm, height=10 * cm)  # type: ignore
                    story.append(img)
                    story.append(Spacer(1, 10))  # type: ignore
            except Exception as e:
                logging.error(f"Erro ao adicionar imagem: {e}")

        # TOP TIPOS DE EVENTO
        if dados["tipos"]:
            story.append(PageBreak())  # type: ignore
            story.append(Paragraph("TOP 5 TIPOS DE EVENTO", subtitulo_style))  # type: ignore
            story.append(Spacer(1, 5))  # type: ignore

            top_tipos = sorted(
                dados["tipos"].items(), key=lambda x: x[1], reverse=True
            )[:5]
            dados_tipos = [["#", "Tipo", "Quantidade"]]
            for i, (tipo, qtd) in enumerate(top_tipos, 1):
                dados_tipos.append([str(i), tipo, str(qtd)])

            tabela_tipos = Table(dados_tipos, colWidths=[1 * cm, 6 * cm, 3 * cm])  # type: ignore
            tabela_tipos.setStyle(
                TableStyle(  # type: ignore
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0d47a1")),  # type: ignore
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),  # type: ignore
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#e3f2fd")),  # type: ignore
                        ("GRID", (0, 0), (-1, -1), 1, HexColor("#0d47a1")),  # type: ignore
                    ]
                )
            )
            story.append(tabela_tipos)
            story.append(Spacer(1, 10))  # type: ignore

        # ULTIMOS EVENTOS
        story.append(PageBreak())  # type: ignore
        story.append(Paragraph("ULTIMOS EVENTOS", subtitulo_style))  # type: ignore
        story.append(Spacer(1, 5))  # type: ignore

        if modulo_selecionado:
            eventos_lista = estado_sistema.eventos_por_modulo.get(
                modulo_selecionado, []
            )
        else:
            eventos_lista = estado_sistema.events

        ultimos = eventos_lista[-20:] if len(eventos_lista) > 20 else eventos_lista

        dados_eventos = [["#", "Data/Hora", "Tipo", "Severidade", "Descricao"]]
        for i, evento in enumerate(reversed(ultimos), 1):
            hora = evento.timestamp.strftime("%d/%m %H:%M")
            tipo = evento.event_type
            sev = ""
            desc = ""
            if isinstance(evento.payload, dict):
                sev = evento.payload.get("severidade", "")
                desc = evento.payload.get("descricao", "")[:40]
            dados_eventos.append([str(i), hora, tipo, sev, desc])

        tabela_eventos = Table(  # type: ignore
            dados_eventos, colWidths=[0.8 * cm, 2.5 * cm, 2.5 * cm, 2 * cm, 5 * cm]  # type: ignore
        )
        tabela_eventos.setStyle(
            TableStyle(  # type: ignore
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0d47a1")),  # type: ignore
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),  # type: ignore
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                    ("BACKGROUND", (0, 1), (-1, -1), HexColor("#e3f2fd")),  # type: ignore
                    ("GRID", (0, 0), (-1, -1), 1, HexColor("#0d47a1")),  # type: ignore
                    ("FONTSIZE", (0, 1), (-1, -1), 7),
                ]
            )
        )
        story.append(tabela_eventos)
        story.append(Spacer(1, 10))  # type: ignore

        # RODAPE
        story.append(Spacer(1, 20))  # type: ignore
        story.append(
            Paragraph(  # type: ignore
                f"Relatorio gerado automaticamente pelo Sistema de Seguranca | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                styles["Italic"],
            )
        )

        doc.build(story)

        # Limpa imagens temporarias
        for imagem in imagens:
            try:
                if Path(imagem).exists():
                    os.remove(imagem)
            except:
                pass

        print(f"\nPDF gerado com sucesso: {caminho_pdf}")

        # Abre o PDF automaticamente
        print("   A abrir PDF automaticamente...")
        if abrir_arquivo_automaticamente(caminho_pdf):
            print("   PDF aberto com sucesso!")
        else:
            print(f"   O PDF esta em: {caminho_pdf}")

        return str(caminho_pdf)

    except Exception as e:
        print(f"[ERRO] Erro ao gerar PDF: {e}")
        logging.error(f"Erro ao gerar PDF: {e}")
        import traceback

        traceback.print_exc()
        return None


# ============================================================
# FUNCAO: gerar_relatorio_analitico()
# ============================================================


def gerar_relatorio_analitico():
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
            for user in utilizadores[:10]:
                linhas.append(f"   - {user}")
            if len(utilizadores) > 10:
                linhas.append(f"   ... e mais {len(utilizadores)-10} utilizadores")
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
                    f"   [{evento.event_type}] {hora} | {modulo} | {descricao[:50]}"
                )
        else:
            linhas.append("   Nenhum evento recente")

        linhas.append("\n" + "=" * 70)

        return "\n".join(linhas)

    except Exception as e:
        return f"[ERRO] {e}"


# ============================================================
# FUNCAO: gerar_relatorio_com_selecao_modulo()
# ============================================================


def gerar_relatorio_com_selecao_modulo():
    global estado_sistema

    if not estado_sistema or not estado_sistema.events:
        print(
            "[ERRO] Nenhum evento carregado. Execute a leitura dos logs primeiro (opcao 6)."
        )
        return

    print("\n" + "=" * 60)
    print("  GERAR RELATORIO PDF COM GRAFICOS")
    print("=" * 60)

    modulos = estado_sistema.get_modulos()

    if not modulos:
        print("[ERRO] Nenhum modulo encontrado!")
        return

    print("\nMODULOS DISPONIVEIS:")
    print("-" * 40)
    for i, mod in enumerate(modulos, 1):
        qtd = len(estado_sistema.eventos_por_modulo[mod])
        print(f"   {i:2}. {mod} - {qtd} eventos")
    print("-" * 40)

    print("\nGerar relatorio por modulo especifico?")
    print("   [s] - Sim, escolher um modulo")
    print("   [n] - Nao, gerar relatorio geral")

    opcao = input("\nEscolha (s/n): ").strip().lower()

    if opcao == "s":
        print("\nSelecione um modulo:")
        print("   Digite o NUMERO ou o NOME do modulo")

        entrada = input("Modulo: ").strip()

        modulo_selecionado = None

        if entrada.isdigit():
            idx = int(entrada) - 1
            if 0 <= idx < len(modulos):
                modulo_selecionado = modulos[idx]
            else:
                print(f"[ERRO] Numero invalido! Use 1 a {len(modulos)}")
                return
        else:
            entrada_upper = entrada.upper().strip()
            for mod in modulos:
                if mod.upper() == entrada_upper:
                    modulo_selecionado = mod
                    break

            if not modulo_selecionado:
                print(f"[ERRO] Modulo '{entrada}' nao encontrado!")
                print(f"   Modulos disponiveis: {', '.join(modulos)}")
                return

        print(f"\nGerando relatorio para o modulo: {modulo_selecionado}")
        gerar_pdf_relatorio(modulo_selecionado)

    elif opcao == "n":
        print("\nGerando relatorio geral do sistema...")
        gerar_pdf_relatorio()

    else:
        print("[ERRO] Opcao invalida! Use 's' ou 'n'")


# ============================================================
# FUNCAO: exportar_csv_simples()
# ============================================================


def exportar_csv_simples():
    """
    Exporta CSV com selecao de modulo
    Colunas: ID, data_hora, status, modulo, observacao, utilizador
    """
    exportar_csv_com_selecao_modulo()


# ============================================================
# FUNCOES AUXILIARES DO MENU
# ============================================================


def _executar_relatorio_analitico():
    """Executa a geracao do relatorio analitico"""
    print("\n" + gerar_relatorio_analitico())


def _reler_logs():
    """Reler os logs da pasta"""
    print("\nA reler logs da pasta...")
    ler_logs_pasta()


# ============================================================
# MENU PRINCIPAL - OTIMIZADO COM TRATAMENTO DE ERROS
# ============================================================


def menu():
    """
    Menu principal - apenas as opcoes numeradas, com tratamento de erros
    """
    while True:
        try:
            print("\n==================================================")
            print("  RELATORIOS - MENU")
            print("==================================================")
            print("")
            print(" 1. Consultar Sistema")
            print(" 2. Detalhar Eventos por Modulo")
            print(" 3. Gerar Relatorio Analitico (Texto)")
            print(" 4. Gerar Relatorio PDF com Graficos")
            print(" 5. Exportar CSV (com selecao de modulo)")
            print(" 6. Reler Logs da Pasta")
            print(" 7. Relatorio de Utilizadores")
            print(" 8. Debug - Verificar eventos carregados")
            print(" 0. Sair")
            print("--------------------------------------------------")

            opcao = input("\nEscolha: ").strip()

            if not opcao:
                continue

            opcao = opcao[0]  # Pega apenas o primeiro caractere

            if opcao == "0":
                logging.info("Modulo de relatorios encerrado")
                print("A sair...")
                break

            # Mapeamento de opcoes
            opcoes = {
                "1": consultar_sistema,
                "2": detalhar_eventos_por_modulo,
                "3": _executar_relatorio_analitico,
                "4": gerar_relatorio_com_selecao_modulo,
                "5": exportar_csv_simples,
                "6": _reler_logs,
                "7": gerar_relatorio_utilizadores,
                "8": debug_logs,
            }

            if opcao in opcoes:
                opcoes[opcao]()
                input("\nPress ENTER para continuar...")
            else:
                print("[ERRO] Opcao invalida!")
                input("\nPress ENTER para continuar...")

        except KeyboardInterrupt:
            print("\n\nOperacao cancelada pelo usuario")
            continue
        except Exception as e:
            logging.error(f"Erro no menu: {e}")
            print(f"[ERRO] {e}")
            input("\nPress ENTER para continuar...")


# ============================================================
# FUNCAO: executar()
# ============================================================


def executar():
    """
    Funcao principal de execucao - TELA TOTALMENTE LIMPA
    Apenas o menu e exibido, sem nenhuma informacao de inicializacao
    """
    # Valida configuracao
    erros = _validar_configuracao()
    if erros:
        for erro in erros:
            print(f"[AVISO] {erro}")

    # Inicializa o estado do sistema em silencio
    estado = EstadoDoSistema()
    inicializar(estado)
    ler_logs_pasta()

    # Menu simplificado - apenas as opcoes
    menu()


# ============================================================
# TESTE LOCAL
# ============================================================

if __name__ == "__main__":
    executar()
