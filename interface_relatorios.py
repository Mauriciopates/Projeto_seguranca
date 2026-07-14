# interface_relatorios.py
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from tkinter import *  # type: ignore
from tkinter import ttk, scrolledtext, messagebox
import io
from contextlib import redirect_stdout
import threading
import traceback
import re
import time
import csv

# Adiciona o diretorio atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# CONFIGURACAO DE BOTOES DE EXPORTACAO POR TIPO DE RELATORIO
# ============================================================

# Configuracao: quais botoes de exportacao estao disponiveis para cada tipo de relatorio
EXPORT_CONFIG = {
    # Formato: "tipo_relatorio": {"pdf": True/False, "csv": True/False}
    "geral": {"pdf": True, "csv": True},           # Consultar Sistema - ambos disponiveis
    "analitico": {"pdf": True, "csv": False},      # Relatorio Analitico - apenas PDF
    "detalhes": {"pdf": True, "csv": True},        # Detalhamento de Eventos - ambos
    "utilizadores": {"pdf": True, "csv": True},    # Relatorio Utilizadores - ambos
    "debug": {"pdf": True, "csv": True},           # Debug - ambos
    "popup": {"pdf": True, "csv": True},           # Padrao para outros popups
}

def obter_export_config(tipo_relatorio):
    """
    Retorna a configuracao de exportacao para um tipo de relatorio.
    
    Args:
        tipo_relatorio (str): O tipo do relatorio (geral, analitico, detalhes, etc)
    
    Returns:
        dict: Configuracao com as chaves 'pdf' e 'csv' (True/False)
    """
    return EXPORT_CONFIG.get(tipo_relatorio, {"pdf": True, "csv": True})

def botao_csv_disponivel(tipo_relatorio):
    """
    Verifica se o botao CSV esta disponivel para o tipo de relatorio.
    
    Args:
        tipo_relatorio (str): O tipo do relatorio
    
    Returns:
        bool: True se CSV estiver disponivel, False caso contrario
    """
    config = obter_export_config(tipo_relatorio)
    return config.get("csv", True)

def botao_pdf_disponivel(tipo_relatorio):
    """
    Verifica se o botao PDF esta disponivel para o tipo de relatorio.
    
    Args:
        tipo_relatorio (str): O tipo do relatorio
    
    Returns:
        bool: True se PDF estiver disponivel, False caso contrario
    """
    config = obter_export_config(tipo_relatorio)
    return config.get("pdf", True)

# ============================================================
# IMPORTACAO PARA CALENDARIO
# ============================================================

try:
    from tkcalendar import DateEntry

    CALENDARIO_DISPONIVEL = True
except ImportError:
    CALENDARIO_DISPONIVEL = False
    print("[AVISO] tkcalendar nao instalado. Execute: pip install tkcalendar")

# ============================================================
# IMPORTACOES DO MODULO RELATORIOS
# ============================================================

from relatorios import (
    estado_sistema,
    consultar_sistema,
    detalhar_eventos_por_modulo,
    gerar_relatorio_analitico,
    ler_logs_pasta,
    gerar_relatorio_utilizadores,
    debug_logs,
    PASTA_LOGS,
    PASTA_RELATORIOS,
    gerar_pdf_relatorio,
    inicializar,
    EstadoDoSistema,
    ultima_leitura,
)

# ============================================================
# CLASSE PRINCIPAL - LAYOUT ESTRUTURADO
# ============================================================


class InterfaceRelatorios:
    def __init__(self, root=None):
        # Configuracao da janela
        if root is None:
            self.root = Tk()
        else:
            self.root = root

        self.root.title("Sistema Integrado de Seguranca - Relatorios")
        self.root.geometry("1300x800")
        self.root.minsize(1100, 700)
        self.root.configure(bg="#e8edf5")

        # Cores - Esquema claro
        self.cores = {
            "bg_principal": "#e8edf5",
            "bg_card": "#ffffff",
            "bg_card_hover": "#f0f4fa",
            "bg_conteudo": "#ffffff",
            "bg_botao": "#1a5c8a",
            "bg_botao_hover": "#2a7cb0",
            "bg_input": "#f0f4fa",
            "texto_principal": "#1a2a4a",
            "texto_secundario": "#4a6a8a",
            "texto_destaque": "#1a6c8a",
            "texto_sucesso": "#2a8a4a",
            "texto_perigo": "#cc3333",
            "texto_aviso": "#cc8800",
            "cor_azul": "#1a6c9a",
            "cor_roxo": "#7a5aaa",
            "cor_borda": "#b0c4d8",
        }

        # Fontes
        self.fontes = {
            "titulo": ("Segoe UI", 22, "bold"),
            "subtitulo": ("Segoe UI", 14, "bold"),
            "normal": ("Segoe UI", 10),
            "botao": ("Segoe UI", 10, "bold"),
            "status": ("Segoe UI", 9),
            "popup_titulo": ("Segoe UI", 16, "bold"),
            "card_valor": ("Segoe UI", 22, "bold"),
            "card_icone": ("Segoe UI", 24),
            "saida": ("Consolas", 10),
        }

        # Variavel para armazenar os eventos e dados extraidos
        self.eventos = []
        self.dados = {
            "total_eventos": 0,
            "modulos": {},
            "utilizadores": set(),
            "critical": 0,
            "warning": 0,
            "info": 0,
        }
        self.eventos_carregados = False

        # Status para filtro de utilizadores
        self.filtro_status = StringVar(value="todos")

        # Armazena o ultimo relatorio gerado para exportacao
        self.ultimo_relatorio = None
        self.ultimo_titulo = ""

        # Cria a interface
        self._criar_interface()

        # Carrega os logs
        self.root.after(100, self._carregar_logs)

    def _log_terminal(self, mensagem, nivel="INFO"):
        """Exibe mensagens no terminal com timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        cores = {
            "INFO": "\033[94m",
            "SUCESSO": "\033[92m",
            "AVISO": "\033[93m",
            "ERRO": "\033[91m",
            "DESTAQUE": "\033[95m",
        }
        reset = "\033[0m"
        cor = cores.get(nivel, "")
        print(f"[{timestamp}] {cor}{nivel}{reset} - {mensagem}")

    # ============================================================
    # FUNCAO OTIMIZADA PARA EXTRAIR UTILIZADORES DOS EVENTOS
    # ============================================================

    def _extrair_utilizadores_dos_eventos(self, eventos):
        """Extrai utilizadores dos eventos de forma otimizada com identificacao de status"""
        self._log_terminal("Extraindo utilizadores dos eventos...", "INFO")

        utilizadores = {}
        desativados = set()
        excluidos = set()
        detalhes_desativacao = {}
        detalhes_exclusao = {}

        total_eventos = len(eventos)
        self._log_terminal(f"Processando {total_eventos} eventos...", "INFO")

        # Compila regex para melhor performance
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
        regex_quem = re.compile(
            r'por\s*[\'"]?([a-zA-Z0-9_\-\.\s]+)[\'"]?', re.IGNORECASE
        )

        for i, evento in enumerate(eventos):
            # Progresso a cada 1000 eventos
            if i % 1000 == 0 and i > 0:
                self._log_terminal(
                    f"Progresso: {i}/{total_eventos} eventos processados", "INFO"
                )

            # Obtem o payload do evento
            payload = self._get_payload(evento)
            if not payload:
                continue

            descricao = str(payload.get("descricao", ""))
            modulo = payload.get("modulo", "")

            # Extrai utilizador do payload ou da descricao
            utilizador = (
                payload.get("utilizador")
                or payload.get("username")
                or payload.get("user")
            )

            if not utilizador:
                # Tenta extrair da descricao
                user_match = regex_utilizador.search(descricao)
                if user_match:
                    utilizador = user_match.group(1)

            if not utilizador or utilizador == "Desconhecido":
                continue

            # Inicializa dados do utilizador
            if utilizador not in utilizadores:
                utilizadores[utilizador] = {
                    "primeiro_evento": self._get_timestamp(evento),
                    "ultimo_evento": self._get_timestamp(evento),
                    "total_eventos": 0,
                    "modulos": set(),
                    "tipos_eventos": set(),
                    "status": "ATIVO",
                    "desativado": False,
                    "excluido": False,
                }

            dados = utilizadores[utilizador]
            dados["total_eventos"] += 1

            timestamp = self._get_timestamp(evento)
            if timestamp < dados["primeiro_evento"]:
                dados["primeiro_evento"] = timestamp
            if timestamp > dados["ultimo_evento"]:
                dados["ultimo_evento"] = timestamp

            if modulo:
                dados["modulos"].add(modulo)

            # Verifica desativacao
            descricao_lower = descricao.lower()
            if regex_desativado.search(descricao_lower):
                user_in_desc = regex_utilizador.search(descricao)
                if user_in_desc and user_in_desc.group(1) == utilizador:
                    desativados.add(utilizador)
                    quem_match = regex_quem.search(descricao)
                    if utilizador not in detalhes_desativacao:
                        detalhes_desativacao[utilizador] = {
                            "data_desativacao": timestamp,
                            "desativado_por": (
                                quem_match.group(1) if quem_match else "Sistema"
                            ),
                            "descricao": descricao[:100],
                            "modulo": modulo,
                        }

            # Verifica exclusao
            if regex_excluido.search(descricao_lower):
                user_in_desc = regex_utilizador.search(descricao)
                if user_in_desc and user_in_desc.group(1) == utilizador:
                    excluidos.add(utilizador)
                    quem_match = regex_quem.search(descricao)
                    if utilizador not in detalhes_exclusao:
                        detalhes_exclusao[utilizador] = {
                            "data_exclusao": timestamp,
                            "excluido_por": (
                                quem_match.group(1) if quem_match else "Sistema"
                            ),
                            "descricao": descricao[:100],
                            "modulo": modulo,
                        }

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

        self._log_terminal(
            f"Extracao concluida! Total: {len(utilizadores)} utilizadores", "SUCESSO"
        )
        ativos = len([u for u, d in utilizadores.items() if d["status"] == "ATIVO"])
        desativados_count = len(
            [u for u, d in utilizadores.items() if d["status"] == "DESATIVADO"]
        )
        excluidos_count = len(
            [u for u, d in utilizadores.items() if d["status"] == "EXCLUIDO"]
        )
        self._log_terminal(f"  Ativos: {ativos}", "INFO")
        self._log_terminal(f"  Desativados: {desativados_count}", "INFO")
        self._log_terminal(f"  Excluidos: {excluidos_count}", "INFO")

        return utilizadores

    # ============================================================
    # FUNCAO PARA EXIBIR RELATORIO DE UTILIZADORES FORMATADO
    # ============================================================

    def _exibir_relatorio_utilizadores(
        self,
        text_area,
        utilizadores,
        status_filtro="todos",
        titulo="RELATORIO DE UTILIZADORES",
        eventos_filtrados=0,
        mostrar_ultimos=False,
    ):
        """Exibe o relatorio de utilizadores formatado na area de texto com todos os detalhes"""
        # Armazena o relatorio para exportacao
        self.ultimo_titulo = titulo

        # Aplica filtro de status
        if status_filtro == "ativos":
            utilizadores_filtrados = {
                u: d for u, d in utilizadores.items() if d["status"] == "ATIVO"
            }
        elif status_filtro == "desativados":
            utilizadores_filtrados = {
                u: d for u, d in utilizadores.items() if d["status"] == "DESATIVADO"
            }
        elif status_filtro == "excluidos":
            utilizadores_filtrados = {
                u: d for u, d in utilizadores.items() if d["status"] == "EXCLUIDO"
            }
        else:
            utilizadores_filtrados = utilizadores

        # Separa por status para o resumo
        todos_ativos = [u for u, d in utilizadores.items() if d["status"] == "ATIVO"]
        todos_desativados = [
            u for u, d in utilizadores.items() if d["status"] == "DESATIVADO"
        ]
        todos_excluidos = [
            u for u, d in utilizadores.items() if d["status"] == "EXCLUIDO"
        ]

        # Ordena por total de eventos (decrescente)
        utilizadores_ordenados = sorted(
            utilizadores_filtrados.items(),
            key=lambda x: x[1]["total_eventos"],
            reverse=True,
        )

        # Se for para mostrar apenas os ultimos, inverte a ordem e pega os 10 primeiros
        if mostrar_ultimos:
            utilizadores_ordenados = sorted(
                utilizadores_filtrados.items(),
                key=lambda x: x[1]["ultimo_evento"],
                reverse=True,
            )[:10]

        total_utilizadores = len(utilizadores)
        total_ativos = len(todos_ativos)
        total_desativados = len(todos_desativados)
        total_excluidos = len(todos_excluidos)
        total_filtrados = len(utilizadores_filtrados)

        # ============================================================
        # CABECALHO DO RELATORIO
        # ============================================================
        text_area.insert(END, "\n" + "=" * 80 + "\n", "titulo")
        text_area.insert(END, f"  {titulo}\n", "titulo")
        text_area.insert(END, "=" * 80 + "\n", "titulo")
        text_area.insert(END, "\n", "info")

        # ============================================================
        # RESUMO
        # ============================================================
        text_area.insert(END, "RESUMO:\n", "subtitulo")
        text_area.insert(
            END,
            f"   Total de utilizadores identificados: {total_utilizadores}\n",
            "info",
        )

        if mostrar_ultimos:
            text_area.insert(
                END,
                f"   Mostrando apenas os ultimos 10 utilizadores (por data de criacao)\n",
                "info",
            )

        # Mostra apenas os status que existem
        if total_ativos > 0:
            text_area.insert(END, f"   Ativos: {total_ativos}\n", "success")
        if total_desativados > 0:
            text_area.insert(
                END, f"   Desativados: {total_desativados}\n", "warning"
            )
        if total_excluidos > 0:
            text_area.insert(END, f"   Excluidos: {total_excluidos}\n", "error")

        text_area.insert(
            END, f"\n   Eventos no periodo: {eventos_filtrados}\n", "info"
        )

        if status_filtro != "todos":
            status_nome = {
                "ativos": "ATIVOS",
                "desativados": "DESATIVADOS",
                "excluidos": "EXCLUIDOS",
            }.get(status_filtro, status_filtro.upper())
            text_area.insert(
                END,
                f"\n   Filtro aplicado: Mostrando apenas {status_nome}\n",
                "info",
            )
            text_area.insert(
                END, f"   Total exibido: {total_filtrados} utilizadores\n", "info"
            )

        # ============================================================
        # TABELA DE UTILIZADORES - DETALHADA
        # ============================================================
        text_area.insert(END, "\n" + "-" * 80 + "\n", "info")

        if utilizadores_ordenados:
            # Cabecalho da tabela
            text_area.insert(
                END,
                f"{'#':<4} | {'Utilizador':<20} | {'Status':<10} | {'Eventos':>8} | {'Ultimo Evento':<20} | {'Modulos':<15}\n",
                "titulo",
            )
            text_area.insert(END, "-" * 80 + "\n", "info")

            # Mostra todos os utilizadores (sem limite de 50)
            for i, (utilizador, dados) in enumerate(utilizadores_ordenados, 1):
                status_icon = (
                    "[ATIVO]"
                    if dados["status"] == "ATIVO"
                    else ("[DESATIVADO]" if dados["status"] == "DESATIVADO" else "[EXCLUIDO]")
                )
                ultimo = dados["ultimo_evento"].strftime("%Y-%m-%d %H:%M")
                modulos_str = ", ".join(list(dados["modulos"])[:3])
                if len(dados["modulos"]) > 3:
                    modulos_str += f" +{len(dados['modulos'])-3}"

                linha = f"{i:<4} | {utilizador[:20]:<20} | {status_icon} | {dados['total_eventos']:>8} | {ultimo:<20} | {modulos_str:<15}\n"
                text_area.insert(END, linha, "info")
        else:
            text_area.insert(
                END,
                "\n   Nenhum utilizador encontrado com o filtro selecionado.\n",
                "warning",
            )

        # ============================================================
        # RODAPE DO RELATORIO
        # ============================================================
        text_area.insert(END, "\n" + "=" * 80 + "\n", "titulo")

        # Legenda
        text_area.insert(END, "\nLEGENDA:\n", "subtitulo")
        text_area.insert(
            END,
            "   [ATIVO] - Utilizador que aparece nos logs (tem eventos registados)\n",
            "success",
        )
        text_area.insert(
            END,
            "   [DESATIVADO] - Identificado por evento de desativacao no log\n",
            "warning",
        )
        text_area.insert(
            END,
            "   [EXCLUIDO] - Identificado por evento de exclusao no log\n",
            "error",
        )
        text_area.insert(END, "\n" + "=" * 80 + "\n", "titulo")

        # Armazena o conteudo para exportacao
        self.ultimo_relatorio = text_area.get(1.0, END)

    def _get_payload(self, evento):
        """Extrai o payload de um evento, seja ele objeto Evento ou tupla"""
        if hasattr(evento, "payload"):
            return evento.payload
        elif isinstance(evento, tuple) and len(evento) >= 2:
            return evento[1]
        elif isinstance(evento, dict):
            return evento
        return None

    def _get_timestamp(self, evento):
        """Extrai o timestamp de um evento"""
        if hasattr(evento, "timestamp"):
            return evento.timestamp
        elif isinstance(evento, tuple) and len(evento) >= 3:
            return evento[2]
        return datetime.now()

    def _extrair_dados_dos_logs(self, eventos):
        """Extrai informacoes de logs de forma otimizada"""
        self._log_terminal("Iniciando extracao de dados dos logs...", "INFO")

        modulos = {}
        utilizadores = set()
        critical = 0
        warning = 0
        info = 0

        total_eventos = len(eventos)
        self._log_terminal(f"Processando {total_eventos} eventos...", "INFO")

        # Compila regex uma unica vez
        regex_modulo = re.compile(
            r"(AUTENTICACAO|BASE_DADOS|CAMARAS|SENSORES)", re.IGNORECASE
        )
        regex_utilizador = re.compile(
            r'(?:utilizador|user|username|usuario|login)[\s\:\=\'"]+([a-zA-Z0-9_\-\.]+)',
            re.IGNORECASE,
        )
        regex_critical = re.compile(
            r"\b(CRITICAL|CRITICO|CRITICO|ERROR|ERRO|CRIT)\b", re.IGNORECASE
        )
        regex_warning = re.compile(r"\b(WARNING|AVISO|WARN)\b", re.IGNORECASE)

        for i, evento in enumerate(eventos):
            # Progresso a cada 1000 eventos
            if i % 1000 == 0 and i > 0:
                self._log_terminal(
                    f"Progresso: {i}/{total_eventos} eventos processados", "INFO"
                )

            # Converte para string
            evento_str = str(evento).upper()
            evento_original = str(evento)

            # 1. EXTRAIR MODULO
            mod_match = regex_modulo.search(evento_str)
            if mod_match:
                modulo = mod_match.group(1).upper()
                modulos[modulo] = modulos.get(modulo, 0) + 1

            # 2. EXTRAIR UTILIZADOR
            user_match = regex_utilizador.search(evento_original)
            if user_match:
                utilizadores.add(user_match.group(1))

            # 3. EXTRAIR SEVERIDADE
            if regex_critical.search(evento_str):
                critical += 1
            elif regex_warning.search(evento_str):
                warning += 1
            else:
                info += 1

        self._log_terminal(
            f"Extracao concluida! Modulos: {len(modulos)}, Utilizadores: {len(utilizadores)}",
            "SUCESSO",
        )
        self._log_terminal(
            f"Severidades - CRITICAL: {critical}, WARNING: {warning}, INFO: {info}",
            "INFO",
        )

        return {
            "modulos": modulos,
            "utilizadores": utilizadores,
            "critical": critical,
            "warning": warning,
            "info": info,
            "total_eventos": len(eventos),
        }

    # ============================================================
    # FUNCAO DE EXPORTACAO CSV GERAL (PARA CONSULTAR SISTEMA)
    # ============================================================

    def _exportar_csv_geral(self, modulo_selecionado=None):
        """Exporta CSV com os dados gerais dos eventos (regra anterior)"""
        try:
            self._log_terminal("Iniciando exportacao CSV geral...", "INFO")

            if not self.eventos:
                messagebox.showerror("Erro", "Nenhum evento carregado!")
                return None

            # Obtem eventos do estado_sistema
            if estado_sistema and estado_sistema.events:
                eventos = estado_sistema.events
            else:
                eventos = self.eventos

            # Filtra por modulo se selecionado
            if modulo_selecionado:
                eventos_filtrados = []
                for evento in eventos:
                    payload = self._get_payload(evento)
                    if payload and payload.get("modulo") == modulo_selecionado:
                        eventos_filtrados.append(evento)
                eventos = eventos_filtrados

                if not eventos:
                    messagebox.showerror(
                        "Erro",
                        f"Nenhum evento encontrado para o modulo {modulo_selecionado}",
                    )
                    return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if modulo_selecionado:
                nome_arquivo = f"csv_{modulo_selecionado}_{timestamp}.csv"
            else:
                nome_arquivo = f"csv_todos_eventos_{timestamp}.csv"

            caminho = PASTA_RELATORIOS / nome_arquivo

            # PREPARAR DADOS
            dados_exportar = []
            for idx, evento in enumerate(eventos, 1):
                payload = self._get_payload(evento)
                timestamp_evento = self._get_timestamp(evento)

                modulo = (
                    payload.get("modulo", "DESCONHECIDO") if payload else "DESCONHECIDO"
                )
                severidade = payload.get("severidade", "INFO") if payload else "INFO"
                descricao = payload.get("descricao", "") if payload else str(evento)
                utilizador = (
                    payload.get("utilizador", "Desconhecido")
                    if payload
                    else "Desconhecido"
                )
                data_hora = (
                    timestamp_evento.strftime("%Y-%m-%d %H:%M:%S")
                    if timestamp_evento
                    else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )

                if severidade == "CRITICAL":
                    status = "CRITICO"
                elif severidade == "WARNING":
                    status = "ATENCAO"
                else:
                    status = "INFO"

                dados_exportar.append(
                    {
                        "id": idx,
                        "data_hora": data_hora,
                        "status": status,
                        "modulo": modulo,
                        "observacao": descricao[:200],
                        "utilizador": utilizador,
                    }
                )

            # ESCREVER CSV
            with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_ALL)
                writer.writerow(
                    ["ID", "Data/Hora", "Status", "Modulo", "Observacao", "Utilizador"]
                )

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

            self._log_terminal(
                f"CSV geral gerado com sucesso: {caminho.name}", "SUCESSO"
            )

            try:
                os.startfile(str(caminho))
            except:
                pass

            messagebox.showinfo(
                "Sucesso",
                f"CSV exportado com sucesso!\n\n"
                f"Arquivo: {caminho.name}\n"
                f"Eventos: {len(dados_exportar)}\n"
                f"Local: {caminho}",
            )
            return str(caminho)

        except Exception as e:
            self._log_terminal(f"ERRO ao exportar CSV geral: {e}", "ERRO")
            messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")
            traceback.print_exc()
            return None

    # ============================================================
    # FUNCAO DE EXPORTACAO CSV DO CONTEUDO DO POPUP (PARA DEMAIS)
    # ============================================================

    def _exportar_csv_popup(self, text_widget, titulo="relatorio"):
        """Exporta o conteudo do popup para CSV (regra para os demais popups)"""
        try:
            self._log_terminal("Iniciando exportacao CSV do popup...", "INFO")

            conteudo = text_widget.get(1.0, END)
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum conteudo para exportar!")
                return None

            # Limpa o nome do titulo para usar no nome do arquivo
            nome_limpo = (
                titulo.replace("RELATORIO", "")
                .replace("DETALHAMENTO", "")
                .replace("CONSULTA", "")
                .replace("ANALITICO", "")
                .replace("DEBUG", "")
                .strip()
            )
            nome_limpo = nome_limpo.replace(" ", "_").lower()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"csv_{nome_limpo}_{timestamp}.csv"
            caminho = PASTA_RELATORIOS / nome_arquivo

            # Processa o conteudo do texto para extrair dados estruturados
            linhas = conteudo.split("\n")

            # Tenta identificar se e uma tabela com pipe separators
            dados_tabela = []
            cabecalho_encontrado = False
            cabecalho = []

            for linha in linhas:
                linha = linha.strip()

                # Procura por linhas com pipe (tabela)
                if "|" in linha and "#" not in linha:
                    # Remove caracteres especiais
                    linha_clean = (
                        linha.replace("[ATIVO]", "")
                        .replace("[DESATIVADO]", "")
                        .replace("[EXCLUIDO]", "")
                        .strip()
                    )

                    # Divide por pipe
                    partes = [p.strip() for p in linha_clean.split("|") if p.strip()]

                    # Verifica se e o cabecalho
                    if "Utilizador" in linha or "Status" in linha or "Eventos" in linha:
                        cabecalho = partes
                        cabecalho_encontrado = True
                        continue

                    # Se encontrou cabecalho e esta linha tem dados
                    if cabecalho_encontrado and len(partes) >= 3:
                        # Remove icones de status
                        partes = [p.replace("●", "").strip() for p in partes]
                        dados_tabela.append(partes)

            # Se nao encontrou tabela, tenta extrair como texto simples
            if not dados_tabela:
                self._log_terminal(
                    "Nenhuma tabela encontrada, exportando como texto...", "INFO"
                )

                # Exporta como texto simples com linhas nao vazias
                with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_ALL)
                    writer.writerow(["Conteudo"])

                    for linha in linhas:
                        linha = linha.strip()
                        if (
                            linha
                            and not linha.startswith("=")
                            and not linha.startswith("-")
                        ):
                            # Remove caracteres especiais
                            linha_clean = (
                                linha.replace("[ATIVO]", "")
                                .replace("[DESATIVADO]", "")
                                .replace("[EXCLUIDO]", "")
                                .strip()
                            )
                            if linha_clean:
                                writer.writerow([linha_clean])

                self._log_terminal(f"CSV texto gerado: {caminho.name}", "SUCESSO")

                try:
                    os.startfile(str(caminho))
                except:
                    pass

                messagebox.showinfo(
                    "Sucesso",
                    f"CSV exportado com sucesso!\n\n"
                    f"Arquivo: {caminho.name}\n"
                    f"Local: {caminho}",
                )
                return str(caminho)

            # Exporta a tabela encontrada
            with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_ALL)

                # Escreve cabecalho
                if cabecalho:
                    writer.writerow(cabecalho)
                else:
                    writer.writerow(
                        [
                            "#",
                            "Utilizador",
                            "Status",
                            "Eventos",
                            "Ultimo_Evento",
                            "Modulos",
                        ]
                    )

                # Escreve os dados
                for linha in dados_tabela:
                    # Garante que todas as linhas tenham o mesmo numero de colunas
                    while len(linha) < len(cabecalho):
                        linha.append("")
                    writer.writerow(linha)

            self._log_terminal(f"CSV tabela gerado: {caminho.name}", "SUCESSO")

            try:
                os.startfile(str(caminho))
            except:
                pass

            messagebox.showinfo(
                "Sucesso",
                f"CSV exportado com sucesso!\n\n"
                f"Arquivo: {caminho.name}\n"
                f"Registros: {len(dados_tabela)}\n"
                f"Local: {caminho}",
            )
            return str(caminho)

        except Exception as e:
            self._log_terminal(f"ERRO ao exportar CSV do popup: {e}", "ERRO")
            messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")
            traceback.print_exc()
            return None

    # ============================================================
    # FUNCAO DE EXPORTACAO PDF GERAL (PARA CONSULTAR SISTEMA)
    # ============================================================

    def _exportar_pdf_geral(self):
        """Exporta o PDF geral do sistema com grafismo profissional"""
        try:
            self._log_terminal("Iniciando exportacao PDF geral do sistema...", "INFO")

            # Verifica se o reportlab esta disponivel
            try:
                import reportlab
                from reportlab.lib.pagesizes import A4, landscape
                from reportlab.platypus import (
                    SimpleDocTemplate,
                    Paragraph,
                    Spacer,
                    Table,
                    TableStyle,
                )
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib import colors
                from reportlab.lib.units import cm
                from reportlab.lib.colors import HexColor
                from reportlab.lib.enums import TA_CENTER, TA_LEFT
                from reportlab.graphics.shapes import Drawing, Line
                from reportlab.graphics.charts.barcharts import VerticalBarChart
                from reportlab.graphics.charts.piecharts import Pie

                print(f"Reportlab versao: {reportlab.__version__}")
            except ImportError as e:
                self._log_terminal(f"ERRO ao importar reportlab: {e}", "ERRO")
                messagebox.showerror(
                    "Erro",
                    f"Biblioteca 'reportlab' nao instalada corretamente.\n"
                    f"Execute: pip install reportlab\n"
                    f"Erro: {e}",
                )
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_pdf = f"relatorio_geral_sistema_{timestamp}.pdf"
            caminho_pdf = PASTA_RELATORIOS / nome_pdf

            # Cores do tema
            cor_primaria = HexColor("#1a5c8a")
            cor_secundaria = HexColor("#2a7cb0")
            cor_destaque = HexColor("#e8edf5")
            cor_texto = HexColor("#1a2a4a")
            cor_borda = HexColor("#b0c4d8")
            cor_sucesso = HexColor("#2a8a4a")
            cor_alerta = HexColor("#cc8800")
            cor_perigo = HexColor("#cc3333")
            cor_roxo = HexColor("#7a5aaa")

            # Cria o PDF
            doc = SimpleDocTemplate(
                str(caminho_pdf),
                pagesize=landscape(A4),
                topMargin=1.8 * cm,
                bottomMargin=1.8 * cm,
                leftMargin=1.8 * cm,
                rightMargin=1.8 * cm,
            )

            story = []
            styles = getSampleStyleSheet()

            # ============================================================
            # ESTILOS PERSONALIZADOS
            # ============================================================

            estilo_titulo_principal = ParagraphStyle(
                "TituloPrincipal",
                parent=styles["Heading1"],
                fontSize=18,
                alignment=TA_CENTER,
                spaceAfter=8,
                textColor=cor_primaria,
                fontName="Helvetica-Bold",
            )

            estilo_subtitulo = ParagraphStyle(
                "Subtitulo",
                parent=styles["Heading2"],
                fontSize=12,
                alignment=TA_CENTER,
                spaceAfter=15,
                textColor=cor_secundaria,
                fontName="Helvetica",
            )

            estilo_titulo_secao = ParagraphStyle(
                "TituloSecao",
                parent=styles["Heading3"],
                fontSize=11,
                alignment=TA_LEFT,
                spaceAfter=6,
                spaceBefore=10,
                textColor=cor_primaria,
                fontName="Helvetica-Bold",
            )

            estilo_normal = ParagraphStyle(
                "NormalPersonalizado",
                parent=styles["Normal"],
                fontSize=9,
                alignment=TA_LEFT,
                textColor=cor_texto,
                fontName="Helvetica",
                leading=12,
            )

            estilo_rodape = ParagraphStyle(
                "Rodape",
                parent=styles["Normal"],
                fontSize=7,
                alignment=TA_CENTER,
                textColor=cor_secundaria,
                fontName="Helvetica-Oblique",
                leading=10,
            )

            estilo_info = ParagraphStyle(
                "Info",
                parent=styles["Normal"],
                fontSize=8,
                alignment=TA_LEFT,
                textColor=HexColor("#4a6a8a"),
                fontName="Helvetica",
                leading=11,
            )

            # ============================================================
            # CABECALHO COM GRAFISMO
            # ============================================================

            # Linha decorativa superior
            linha_superior = Drawing(720, 4)
            linha_superior.add(
                Line(0, 2, 720, 2, strokeColor=cor_primaria, strokeWidth=2)
            )
            story.append(linha_superior)
            story.append(Spacer(1, 8))

            # Titulo principal
            story.append(Paragraph("SISTEMA DE SEGURANCA", estilo_titulo_principal))
            story.append(Paragraph("Relatorio Geral do Sistema", estilo_subtitulo))

            # Linha decorativa dupla
            linha_dupla = Drawing(720, 8)
            linha_dupla.add(
                Line(100, 4, 620, 4, strokeColor=cor_primaria, strokeWidth=1.5)
            )
            linha_dupla.add(
                Line(150, 2, 570, 2, strokeColor=cor_secundaria, strokeWidth=0.5)
            )
            story.append(linha_dupla)
            story.append(Spacer(1, 10))

            # Informacoes do relatorio
            dados_cabecalho = [
                ["Titulo:", "Relatorio Geral do Sistema"],
                ["Data:", datetime.now().strftime("%d/%m/%Y %H:%M:%S")],
                [
                    "Documento:",
                    f"REL-GERAL-{datetime.now().strftime('%Y%m%d')}-{timestamp[-4:]}",
                ],
            ]

            tabela_cabecalho = Table(dados_cabecalho, colWidths=[3 * cm, 10 * cm])
            tabela_cabecalho.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("TEXTCOLOR", (0, 0), (0, -1), cor_primaria),
                        ("TEXTCOLOR", (1, 0), (1, -1), cor_texto),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEADING", (0, 0), (-1, -1), 14),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                        ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ]
                )
            )
            story.append(tabela_cabecalho)
            story.append(Spacer(1, 12))

            # ============================================================
            # DADOS DO SISTEMA
            # ============================================================

            # Obtem dados gerais
            total_eventos = self.dados.get("total_eventos", 0)
            critical = self.dados.get("critical", 0)
            warning = self.dados.get("warning", 0)
            info = self.dados.get("info", 0)
            modulos = self.dados.get("modulos", {})
            utilizadores = self.dados.get("utilizadores", set())
            total_utilizadores = len(utilizadores)

            # Tabela de resumo geral
            story.append(Paragraph("RESUMO GERAL DO SISTEMA", estilo_titulo_secao))

            resumo_dados = [
                ["Metrica", "Valor", "Detalhe"],
                ["Total de Eventos", f"{total_eventos}", "Todos os eventos registados"],
                ["Eventos Criticos", f"{critical}", "Requer atencao imediata"],
                ["Eventos de Alerta", f"{warning}", "Monitoramento recomendado"],
                ["Eventos Informativos", f"{info}", "Registos normais do sistema"],
                [
                    "Total de Utilizadores",
                    f"{total_utilizadores}",
                    "Identificados nos logs",
                ],
                [
                    "Modulos Ativos",
                    f"{len(modulos)}",
                    f"{', '.join(modulos.keys()) if modulos else 'Nenhum'}",
                ],
            ]

            tabela_resumo = Table(resumo_dados, colWidths=[4 * cm, 3 * cm, 8 * cm])
            tabela_resumo.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("BACKGROUND", (0, 0), (-1, 0), cor_primaria),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("BACKGROUND", (0, 1), (-1, 5), HexColor("#f5f8fc")),
                        ("TEXTCOLOR", (0, 1), (-1, -1), cor_texto),
                        ("GRID", (0, 0), (-1, -1), 0.5, cor_borda),
                        ("ALIGN", (0, 0), (1, -1), "CENTER"),
                        ("ALIGN", (2, 0), (2, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        (
                            "TEXTCOLOR",
                            (1, 2),
                            (1, 2),
                            cor_perigo if critical > 0 else cor_texto,
                        ),
                        (
                            "TEXTCOLOR",
                            (1, 3),
                            (1, 3),
                            cor_alerta if warning > 0 else cor_texto,
                        ),
                    ]
                )
            )
            story.append(tabela_resumo)
            story.append(Spacer(1, 15))

            # ============================================================
            # GRAFICO DE BARRAS - EVENTOS POR MODULO
            # ============================================================

            if modulos:
                story.append(
                    Paragraph(
                        "DISTRIBUICAO DE EVENTOS POR MODULO", estilo_titulo_secao
                    )
                )
                story.append(Spacer(1, 5))

                # Prepara dados para o grafico
                modulo_nomes = list(modulos.keys())
                modulo_valores = list(modulos.values())

                # Cria grafico de barras
                drawing = Drawing(700, 200)

                bar_chart = VerticalBarChart()
                bar_chart.x = 50
                bar_chart.y = 30
                bar_chart.width = 600
                bar_chart.height = 150
                bar_chart.data = [modulo_valores]
                bar_chart.categoryAxis.categoryNames = modulo_nomes
                bar_chart.categoryAxis.labels.fontSize = 8
                bar_chart.categoryAxis.labels.angle = 45
                bar_chart.valueAxis.valueMin = 0
                bar_chart.valueAxis.valueMax = (
                    max(modulo_valores) * 1.2 if modulo_valores else 10
                )
                bar_chart.valueAxis.valueStep = (
                    max(1, int(max(modulo_valores) / 5)) if modulo_valores else 1
                )

                # Cores para as barras
                cores_barras = [
                    cor_primaria,
                    cor_secundaria,
                    cor_roxo,
                    cor_sucesso,
                    cor_alerta,
                ]
                for i in range(len(modulo_valores)):
                    if i < len(cores_barras):
                        bar_chart.bars[i].fillColor = cores_barras[i]
                    bar_chart.bars[i].strokeColor = cor_secundaria
                    bar_chart.bars[i].strokeWidth = 1

                drawing.add(bar_chart)
                story.append(drawing)
                story.append(Spacer(1, 15))

            # ============================================================
            # GRAFICO DE PIZZA - SEVERIDADE DOS EVENTOS
            # ============================================================

            if total_eventos > 0:
                story.append(
                    Paragraph("DISTRIBUICAO POR SEVERIDADE", estilo_titulo_secao)
                )
                story.append(Spacer(1, 5))

                # Cria grafico de pizza
                pie_drawing = Drawing(400, 250)
                pie = Pie()
                pie.x = 100
                pie.y = 30
                pie.width = 200
                pie.height = 200
                pie.data = [critical, warning, info]
                pie.labels = [
                    f"Critico ({critical})",
                    f"Alerta ({warning})",
                    f"Info ({info})",
                ]
                pie.slices.strokeWidth = 0.5
                pie.slices[0].fillColor = cor_perigo
                pie.slices[1].fillColor = cor_alerta
                pie.slices[2].fillColor = cor_primaria
                if critical > 0:
                    pie.slices[0].popout = 5
                if warning > 0:
                    pie.slices[1].popout = 3

                pie_drawing.add(pie)
                story.append(pie_drawing)
                story.append(Spacer(1, 15))

            # ============================================================
            # LISTA DE MODULOS COM DETALHES
            # ============================================================

            if modulos:
                story.append(Paragraph("DETALHES DOS MODULOS", estilo_titulo_secao))
                story.append(Spacer(1, 5))

                # Tabela de modulos
                modulo_dados = [["Modulo", "Total de Eventos", "Percentual"]]
                total_modulos_eventos = sum(modulos.values())

                for modulo, quantidade in sorted(
                    modulos.items(), key=lambda x: x[1], reverse=True
                ):
                    percentual = (
                        (quantidade / total_modulos_eventos * 100)
                        if total_modulos_eventos > 0
                        else 0
                    )
                    modulo_dados.append([modulo, str(quantidade), f"{percentual:.1f}%"])

                tabela_modulos = Table(modulo_dados, colWidths=[5 * cm, 4 * cm, 4 * cm])
                tabela_modulos.setStyle(
                    TableStyle(
                        [
                            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("BACKGROUND", (0, 0), (-1, 0), cor_primaria),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("BACKGROUND", (0, 1), (-1, -1), HexColor("#f5f8fc")),
                            ("TEXTCOLOR", (0, 1), (-1, -1), cor_texto),
                            ("GRID", (0, 0), (-1, -1), 0.5, cor_borda),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                # Alterna cores das linhas
                for i in range(1, len(modulo_dados)):
                    if i % 2 == 0:
                        tabela_modulos.setStyle(
                            TableStyle(
                                [("BACKGROUND", (0, i), (-1, i), HexColor("#e8edf5"))]
                            )
                        )
                story.append(tabela_modulos)
                story.append(Spacer(1, 15))

            # ============================================================
            # LISTA DE UTILIZADORES (ULTIMOS 10)
            # ============================================================

            if utilizadores:
                story.append(
                    Paragraph("ULTIMOS 10 UTILIZADORES CRIADOS", estilo_titulo_secao)
                )
                story.append(Spacer(1, 5))

                # Converte para lista ordenada por data de criacao (mais recentes primeiro)
                # Como nao temos data de criacao, usamos o ultimo evento como referencia
                utilizadores_com_data = []
                for user in utilizadores:
                    # Tenta obter a data do ultimo evento do utilizador
                    data = None
                    for evento in self.eventos:
                        payload = self._get_payload(evento)
                        if payload:
                            user_payload = payload.get("utilizador") or payload.get("username") or payload.get("user")
                            if user_payload == user:
                                data = self._get_timestamp(evento)
                                break
                    
                    if data is None:
                        data = datetime.now()
                    
                    utilizadores_com_data.append((user, data))
                
                # Ordena por data (mais recente primeiro)
                utilizadores_com_data.sort(key=lambda x: x[1], reverse=True)
                
                # Pega os 10 ultimos
                ultimos_10 = utilizadores_com_data[:10]
                
                # Cria tabela de utilizadores
                user_dados = [["#", "Utilizador", "Ultima Atividade"]]
                for i, (user, data) in enumerate(ultimos_10, 1):
                    data_str = data.strftime("%Y-%m-%d %H:%M") if isinstance(data, datetime) else str(data)
                    user_dados.append([str(i), user, data_str])

                if total_utilizadores > 10:
                    user_dados.append(
                        ["", f"... e mais {total_utilizadores - 10} utilizadores", ""]
                    )

                tabela_users = Table(user_dados, colWidths=[2 * cm, 5 * cm, 4 * cm])
                tabela_users.setStyle(
                    TableStyle(
                        [
                            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("BACKGROUND", (0, 0), (-1, 0), cor_primaria),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.5, cor_borda),
                            ("ALIGN", (0, 0), (0, -1), "CENTER"),
                            ("ALIGN", (1, 0), (1, -1), "LEFT"),
                            ("ALIGN", (2, 0), (2, -1), "CENTER"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ]
                    )
                )
                # Alterna cores das linhas
                for i in range(1, len(user_dados)):
                    if i % 2 == 0:
                        tabela_users.setStyle(
                            TableStyle(
                                [("BACKGROUND", (0, i), (-1, i), HexColor("#e8edf5"))]
                            )
                        )
                story.append(tabela_users)
                story.append(Spacer(1, 15))

            # ============================================================
            # RODAPE COM GRAFISMO
            # ============================================================

            story.append(Spacer(1, 20))

            # Linha decorativa inferior
            linha_inferior = Drawing(720, 4)
            linha_inferior.add(
                Line(0, 2, 720, 2, strokeColor=cor_primaria, strokeWidth=1.5)
            )
            story.append(linha_inferior)
            story.append(Spacer(1, 8))

            # Rodape
            story.append(
                Paragraph(
                    f"Relatorio geral gerado automaticamente pelo Sistema Integrado de Seguranca",
                    estilo_rodape,
                )
            )
            story.append(
                Paragraph(
                    f"Documento: REL-GERAL-{datetime.now().strftime('%Y%m%d')}-{timestamp[-4:]} | Versao: 1.0",
                    estilo_rodape,
                )
            )
            story.append(
                Paragraph(
                    f"© {datetime.now().year} - Todos os direitos reservados",
                    estilo_rodape,
                )
            )

            # ============================================================
            # GERA O PDF
            # ============================================================

            doc.build(story)

            self._log_terminal(
                f"PDF geral gerado com sucesso: {caminho_pdf.name}", "SUCESSO"
            )

            try:
                os.startfile(str(caminho_pdf))
            except:
                pass

            messagebox.showinfo(
                "Sucesso",
                f"PDF geral exportado com sucesso!\n\n"
                f"Arquivo: {caminho_pdf.name}\n"
                f"Local: {caminho_pdf}",
            )

        except Exception as e:
            self._log_terminal(f"ERRO ao exportar PDF geral: {e}", "ERRO")
            import traceback

            traceback.print_exc()
            messagebox.showerror(
                "Erro", f"Erro ao exportar PDF: {e}\n\n{traceback.format_exc()}"
            )

    # ============================================================
    # FUNCAO DE EXPORTACAO PDF DO RELATORIO ATUAL COM GRAFISMO (PARA DEMAIS)
    # ============================================================

    def _exportar_pdf_relatorio_atual(self, conteudo=None, titulo="Relatorio"):
        """Exporta o relatorio atual (o que esta na tela) para PDF com grafismo profissional"""
        try:
            if conteudo is None:
                conteudo = self.ultimo_relatorio

            if not conteudo or conteudo.strip() == "":
                messagebox.showerror(
                    "Erro",
                    "Nenhum relatorio para exportar! Execute uma consulta primeiro.",
                )
                return

            self._log_terminal("Iniciando exportacao PDF do relatorio atual...", "INFO")

            # Verifica se o reportlab esta disponivel
            try:
                from reportlab.lib.pagesizes import A4, landscape
                from reportlab.platypus import (
                    SimpleDocTemplate,
                    Paragraph,
                    Spacer,
                    Table,
                    TableStyle,
                )
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib import colors
                from reportlab.lib.units import cm
                from reportlab.lib.colors import HexColor
                from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
                from reportlab.graphics.shapes import Drawing, Line, Rect
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
            except ImportError as e:
                self._log_terminal(f"ERRO ao importar reportlab: {e}", "ERRO")
                messagebox.showerror(
                    "Erro",
                    f"Biblioteca 'reportlab' nao instalada corretamente.\n"
                    f"Execute: pip install reportlab\n"
                    f"Erro: {e}",
                )
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_pdf = f"relatorio_{timestamp}.pdf"
            caminho_pdf = PASTA_RELATORIOS / nome_pdf

            # Cores do tema - esquema mais moderno
            cor_primaria = HexColor("#1a5276")
            cor_secundaria = HexColor("#2980b9")
            cor_destaque = HexColor("#eaf2f8")
            cor_texto = HexColor("#1a2a4a")
            cor_texto_claro = HexColor("#5d6d7e")
            cor_borda = HexColor("#b0c4d8")
            cor_sucesso = HexColor("#27ae60")
            cor_alerta = HexColor("#f39c12")
            cor_perigo = HexColor("#e74c3c")
            cor_roxo = HexColor("#8e44ad")
            cor_fundo_tabela = HexColor("#f8f9fa")
            cor_titulo_tabela = HexColor("#1a5276")

            # Cria o PDF
            doc = SimpleDocTemplate(
                str(caminho_pdf),
                pagesize=landscape(A4),
                topMargin=1.5 * cm,
                bottomMargin=1.5 * cm,
                leftMargin=1.5 * cm,
                rightMargin=1.5 * cm,
            )

            story = []
            styles = getSampleStyleSheet()

            # ============================================================
            # ESTILOS PERSONALIZADOS
            # ============================================================

            estilo_titulo_principal = ParagraphStyle(
                "TituloPrincipal",
                parent=styles["Heading1"],
                fontSize=20,
                alignment=TA_CENTER,
                spaceAfter=6,
                textColor=cor_primaria,
                fontName="Helvetica-Bold",
            )

            estilo_subtitulo = ParagraphStyle(
                "Subtitulo",
                parent=styles["Heading2"],
                fontSize=13,
                alignment=TA_CENTER,
                spaceAfter=12,
                textColor=cor_secundaria,
                fontName="Helvetica",
            )

            estilo_titulo_secao = ParagraphStyle(
                "TituloSecao",
                parent=styles["Heading3"],
                fontSize=12,
                alignment=TA_LEFT,
                spaceAfter=5,
                spaceBefore=8,
                textColor=cor_primaria,
                fontName="Helvetica-Bold",
            )

            estilo_normal = ParagraphStyle(
                "NormalPersonalizado",
                parent=styles["Normal"],
                fontSize=9,
                alignment=TA_LEFT,
                textColor=cor_texto,
                fontName="Helvetica",
                leading=14,
            )

            estilo_rodape = ParagraphStyle(
                "Rodape",
                parent=styles["Normal"],
                fontSize=7,
                alignment=TA_CENTER,
                textColor=cor_texto_claro,
                fontName="Helvetica-Oblique",
                leading=10,
            )

            estilo_info = ParagraphStyle(
                "Info",
                parent=styles["Normal"],
                fontSize=8,
                alignment=TA_LEFT,
                textColor=cor_texto_claro,
                fontName="Helvetica",
                leading=12,
            )

            estilo_item = ParagraphStyle(
                "Item",
                parent=styles["Normal"],
                fontSize=9,
                alignment=TA_LEFT,
                textColor=cor_texto,
                fontName="Helvetica",
                leading=14,
                leftIndent=15,
            )

            estilo_resumo = ParagraphStyle(
                "Resumo",
                parent=styles["Normal"],
                fontSize=9,
                alignment=TA_LEFT,
                textColor=cor_texto,
                fontName="Helvetica",
                leading=15,
                leftIndent=10,
            )

            estilo_valor_destaque = ParagraphStyle(
                "ValorDestaque",
                parent=styles["Normal"],
                fontSize=11,
                alignment=TA_LEFT,
                textColor=cor_secundaria,
                fontName="Helvetica-Bold",
                leading=16,
                leftIndent=20,
            )

            # ============================================================
            # CABECALHO COM GRAFISMO MODERNO
            # ============================================================

            # Fundo decorativo do cabecalho
            cabecalho_fundo = Drawing(720, 60)
            cabecalho_fundo.add(
                Rect(0, 0, 720, 60, fillColor=cor_destaque, strokeColor=cor_primaria, strokeWidth=1) # type: ignore
            )
            story.append(cabecalho_fundo)
            story.append(Spacer(1, -55))

            # Titulo principal
            story.append(Paragraph("SISTEMA INTEGRADO DE SEGURANCA", estilo_titulo_principal))
            story.append(Paragraph("Relatorio de Auditoria", estilo_subtitulo))

            # Linha decorativa
            linha_decorativa = Drawing(720, 4)
            linha_decorativa.add(
                Line(150, 2, 570, 2, strokeColor=cor_primaria, strokeWidth=2)
            )
            story.append(linha_decorativa)
            story.append(Spacer(1, 8))

            # Informacoes do relatorio em tabela estilizada
            dados_cabecalho = [
                ["Titulo:", titulo],
                ["Data:", datetime.now().strftime("%d/%m/%Y %H:%M:%S")],
                [
                    "Documento:",
                    f"REL-{datetime.now().strftime('%Y%m%d')}-{timestamp[-4:]}",
                ],
            ]

            tabela_cabecalho = Table(dados_cabecalho, colWidths=[3 * cm, 10 * cm])
            tabela_cabecalho.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("TEXTCOLOR", (0, 0), (0, -1), cor_primaria),
                        ("TEXTCOLOR", (1, 0), (1, -1), cor_texto),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEADING", (0, 0), (-1, -1), 14),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                        ("ALIGN", (1, 0), (1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ]
                )
            )
            story.append(tabela_cabecalho)
            story.append(Spacer(1, 10))

            # Linha separadora
            linha_separadora = Drawing(720, 2)
            linha_separadora.add(
                Line(0, 1, 720, 1, strokeColor=cor_borda, strokeWidth=0.5)
            )
            story.append(linha_separadora)
            story.append(Spacer(1, 8))

            # ============================================================
            # CONTEUDO DO RELATORIO
            # ============================================================

            # Processa o texto do relatorio
            linhas = conteudo.split("\n")

            # Variaveis para controle de secao
            na_secao_estatisticas = False
            na_secao_modulos = False
            na_secao_utilizadores = False
            na_secao_eventos_por_tipo = False
            na_secao_ultimos_eventos = False
            
            estatisticas_linhas = []
            modulos_linhas = []
            utilizadores_lista = []
            eventos_por_tipo = []
            ultimos_eventos = []

            # Primeira passagem para coletar todas as secoes
            for linha in linhas:
                linha = linha.strip()
                
                # Detecta secao 1: ESTATISTICAS GERAIS
                if "1. ESTATISTICAS GERAIS" in linha or "ESTATISTICAS GERAIS" in linha.upper():
                    na_secao_estatisticas = True
                    na_secao_modulos = False
                    na_secao_utilizadores = False
                    na_secao_eventos_por_tipo = False
                    na_secao_ultimos_eventos = False
                    continue
                
                # Detecta secao 2: MODULOS ENCONTRADOS
                if "2. MODULOS ENCONTRADOS" in linha:
                    na_secao_estatisticas = False
                    na_secao_modulos = True
                    na_secao_utilizadores = False
                    na_secao_eventos_por_tipo = False
                    na_secao_ultimos_eventos = False
                    continue
                
                # Detecta secao 3: UTILIZADORES
                if "3. UTILIZADORES" in linha:
                    na_secao_estatisticas = False
                    na_secao_modulos = False
                    na_secao_utilizadores = True
                    na_secao_eventos_por_tipo = False
                    na_secao_ultimos_eventos = False
                    continue
                
                # Detecta secao 4: EVENTOS POR TIPO
                if "4. EVENTOS POR TIPO" in linha:
                    na_secao_estatisticas = False
                    na_secao_modulos = False
                    na_secao_utilizadores = False
                    na_secao_eventos_por_tipo = True
                    na_secao_ultimos_eventos = False
                    continue
                
                # Detecta secao 5: ULTIMOS EVENTOS
                if "5. ULTIMOS EVENTOS" in linha:
                    na_secao_estatisticas = False
                    na_secao_modulos = False
                    na_secao_utilizadores = False
                    na_secao_eventos_por_tipo = False
                    na_secao_ultimos_eventos = True
                    continue
                
                # Coleta estatisticas
                if na_secao_estatisticas:
                    if linha and not linha.startswith("=") and not linha.startswith("-"):
                        estatisticas_linhas.append(linha)
                    continue
                
                # Coleta modulos
                if na_secao_modulos:
                    if linha and not linha.startswith("=") and not linha.startswith("-"):
                        modulos_linhas.append(linha)
                    continue
                
                # Coleta utilizadores
                if na_secao_utilizadores:
                    if linha.startswith("- ") or (linha.strip() and not linha.startswith("...") and not linha.startswith("=") and not linha.startswith("-")):
                        user = linha.replace("- ", "").strip()
                        if user and not user.startswith("..."):
                            utilizadores_lista.append(user)
                        continue
                    if linha.startswith("..."):
                        continue
                
                # Coleta eventos por tipo
                if na_secao_eventos_por_tipo:
                    if linha and not linha.startswith("-") and not linha.startswith("=") and ":" in linha:
                        partes = linha.split(":")
                        if len(partes) >= 2:
                            tipo = partes[0].strip()
                            valor = partes[1].strip()
                            eventos_por_tipo.append((tipo, valor))
                        continue
                
                # Coleta ultimos eventos
                if na_secao_ultimos_eventos:
                    if linha.startswith("[") and "|" in linha:
                        ultimos_eventos.append(linha)
                        continue

            # ============================================================
            # SECAO 1: ESTATISTICAS GERAIS
            # ============================================================
            
            if estatisticas_linhas:
                story.append(
                    Paragraph("1. ESTATISTICAS GERAIS", estilo_titulo_secao)
                )
                story.append(Spacer(1, 3))
                
                # Exibe as linhas das estatisticas com destaque
                for linha in estatisticas_linhas[:20]:
                    if linha.strip():
                        if ":" in linha:
                            partes = linha.split(":")
                            if len(partes) >= 2:
                                chave = partes[0].strip()
                                valor = partes[1].strip()
                                story.append(Paragraph(f"{chave}: {valor}", estilo_valor_destaque))
                            else:
                                story.append(Paragraph(linha[:200], estilo_resumo))
                        else:
                            story.append(Paragraph(linha[:200], estilo_resumo))
                        story.append(Spacer(1, 2))
                
                story.append(Spacer(1, 8))

            # ============================================================
            # SECAO 2: MODULOS ENCONTRADOS
            # ============================================================
            
            if modulos_linhas:
                story.append(Spacer(1, 5))
                story.append(
                    Paragraph("2. MODULOS ENCONTRADOS", estilo_titulo_secao)
                )
                story.append(Spacer(1, 3))
                
                # Cria tabela com modulos
                modulos_dados = [["Modulo", "Eventos"]]
                for linha in modulos_linhas:
                    if ":" in linha:
                        partes = linha.split(":")
                        if len(partes) >= 2:
                            modulo = partes[0].strip()
                            eventos = partes[1].strip().replace("eventos", "").strip()
                            modulos_dados.append([modulo, eventos])
                
                if len(modulos_dados) > 1:
                    # Calcula a largura das colunas
                    tabela_modulos = Table(modulos_dados, colWidths=[8 * cm, 5 * cm])
                    tabela_modulos.setStyle(
                        TableStyle(
                            [
                                # Cabecalho
                                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                ("FONTSIZE", (0, 0), (-1, 0), 9),
                                ("BACKGROUND", (0, 0), (-1, 0), cor_titulo_tabela),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                # Dados
                                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                                ("FONTSIZE", (0, 1), (-1, -1), 9),
                                ("BACKGROUND", (0, 1), (-1, -1), cor_fundo_tabela),
                                ("TEXTCOLOR", (0, 1), (-1, -1), cor_texto),
                                # Bordas
                                ("GRID", (0, 0), (-1, -1), 0.5, cor_borda),
                                # Alinhamento
                                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                # Padding
                                ("TOPPADDING", (0, 0), (-1, -1), 5),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                            ]
                        )
                    )
                    # Alterna cores das linhas
                    for i in range(1, len(modulos_dados)):
                        if i % 2 == 0:
                            tabela_modulos.setStyle(
                                TableStyle(
                                    [("BACKGROUND", (0, i), (-1, i), HexColor("#e8f4f8"))]
                                )
                            )
                    story.append(tabela_modulos)
                
                story.append(Spacer(1, 8))

            # ============================================================
            # SECAO 3: ULTIMOS 10 UTILIZADORES CRIADOS
            # ============================================================
            
            if utilizadores_lista:
                story.append(Spacer(1, 5))
                story.append(
                    Paragraph("3. ULTIMOS 10 UTILIZADORES CRIADOS", estilo_titulo_secao)
                )
                story.append(Spacer(1, 3))
                
                # Pega os 10 ultimos
                ultimos_10 = utilizadores_lista[:10]
                
                # Cria tabela com os ultimos 10 utilizadores
                user_dados = [["#", "Utilizador"]]
                for i, user in enumerate(ultimos_10, 1):
                    user_dados.append([str(i), user])
                
                if len(utilizadores_lista) > 10:
                    user_dados.append(
                        ["", f"... e mais {len(utilizadores_lista) - 10} utilizadores"]
                    )
                
                tabela_ultimos = Table(user_dados, colWidths=[2.5 * cm, 10.5 * cm])
                tabela_ultimos.setStyle(
                    TableStyle(
                        [
                            # Cabecalho
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 9),
                            ("BACKGROUND", (0, 0), (-1, 0), cor_titulo_tabela),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            # Dados
                            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 1), (-1, -1), 9),
                            ("BACKGROUND", (0, 1), (-1, -1), cor_fundo_tabela),
                            ("TEXTCOLOR", (0, 1), (-1, -1), cor_texto),
                            # Bordas
                            ("GRID", (0, 0), (-1, -1), 0.5, cor_borda),
                            # Alinhamento
                            ("ALIGN", (0, 0), (0, -1), "CENTER"),
                            ("ALIGN", (1, 0), (1, -1), "LEFT"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            # Padding
                            ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ]
                    )
                )
                # Alterna cores das linhas
                for i in range(1, len(user_dados)):
                    if i % 2 == 0:
                        tabela_ultimos.setStyle(
                            TableStyle(
                                [("BACKGROUND", (0, i), (-1, i), HexColor("#e8f4f8"))]
                            )
                        )
                story.append(tabela_ultimos)
                story.append(Spacer(1, 8))

            # ============================================================
            # SECAO 4: EVENTOS POR TIPO
            # ============================================================
            
            if eventos_por_tipo:
                story.append(Spacer(1, 5))
                story.append(
                    Paragraph("4. EVENTOS POR TIPO", estilo_titulo_secao)
                )
                story.append(Spacer(1, 3))
                
                # Cria tabela com eventos por tipo
                tipo_dados = [["Tipo", "Quantidade"]]
                for tipo, valor in eventos_por_tipo:
                    tipo_dados.append([tipo, valor])
                
                tabela_tipos = Table(tipo_dados, colWidths=[8 * cm, 5 * cm])
                tabela_tipos.setStyle(
                    TableStyle(
                        [
                            # Cabecalho
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 9),
                            ("BACKGROUND", (0, 0), (-1, 0), cor_titulo_tabela),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            # Dados
                            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 1), (-1, -1), 9),
                            ("BACKGROUND", (0, 1), (-1, -1), cor_fundo_tabela),
                            ("TEXTCOLOR", (0, 1), (-1, -1), cor_texto),
                            # Bordas
                            ("GRID", (0, 0), (-1, -1), 0.5, cor_borda),
                            # Alinhamento
                            ("ALIGN", (0, 0), (0, -1), "LEFT"),
                            ("ALIGN", (1, 0), (1, -1), "CENTER"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            # Padding
                            ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ]
                    )
                )
                # Alterna cores das linhas
                for i in range(1, len(tipo_dados)):
                    if i % 2 == 0:
                        tabela_tipos.setStyle(
                            TableStyle(
                                [("BACKGROUND", (0, i), (-1, i), HexColor("#e8f4f8"))]
                            )
                        )
                story.append(tabela_tipos)
                story.append(Spacer(1, 8))

            # ============================================================
            # SECAO 5: ULTIMOS EVENTOS
            # ============================================================
            
            if ultimos_eventos:
                story.append(Spacer(1, 5))
                story.append(
                    Paragraph("5. ULTIMOS EVENTOS", estilo_titulo_secao)
                )
                story.append(Spacer(1, 3))
                
                # Mostra os ultimos eventos em formato de lista com asteriscos
                for evento in ultimos_eventos[:20]:
                    evento_formatado = f"* {evento}"
                    story.append(Paragraph(evento_formatado[:200], estilo_item))
                    story.append(Spacer(1, 1))
                
                if len(ultimos_eventos) > 20:
                    story.append(
                        Paragraph(f"... e mais {len(ultimos_eventos) - 20} eventos", estilo_info)
                    )
                
                story.append(Spacer(1, 8))

            # ============================================================
            # RODAPE COM GRAFISMO
            # ============================================================

            story.append(Spacer(1, 15))

            # Linha decorativa inferior
            linha_inferior = Drawing(720, 4)
            linha_inferior.add(
                Line(0, 2, 720, 2, strokeColor=cor_primaria, strokeWidth=1.5)
            )
            story.append(linha_inferior)
            story.append(Spacer(1, 6))

            # Rodape
            story.append(
                Paragraph(
                    f"Relatorio gerado automaticamente pelo Sistema Integrado de Seguranca",
                    estilo_rodape,
                )
            )
            story.append(
                Paragraph(
                    f"Documento: REL-{datetime.now().strftime('%Y%m%d')}-{timestamp[-4:]} | Versao: 1.0",
                    estilo_rodape,
                )
            )
            story.append(
                Paragraph(
                    f"© {datetime.now().year} - Todos os direitos reservados",
                    estilo_rodape,
                )
            )

            # ============================================================
            # GERA O PDF
            # ============================================================

            doc.build(story)

            self._log_terminal(f"PDF gerado com sucesso: {caminho_pdf.name}", "SUCESSO")

            try:
                os.startfile(str(caminho_pdf))
            except:
                pass

            messagebox.showinfo(
                "Sucesso",
                f"PDF exportado com sucesso!\n\n"
                f"Arquivo: {caminho_pdf.name}\n"
                f"Local: {caminho_pdf}",
            )

        except Exception as e:
            self._log_terminal(f"ERRO ao exportar PDF: {e}", "ERRO")
            import traceback

            traceback.print_exc()
            messagebox.showerror(
                "Erro", f"Erro ao exportar PDF: {e}\n\n{traceback.format_exc()}"
            )    
   
    # ============================================================
    # FUNCAO DE EXPORTACAO PDF DO CONTEUDO DE UM POPUP
    # ============================================================

    def _exportar_pdf_popup(self, text_widget, titulo="Relatorio"):
        """Exporta o conteudo de um widget de texto para PDF"""
        try:
            conteudo = text_widget.get(1.0, END)
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror(
                    "Erro",
                    "Nenhum conteudo para exportar!",
                )
                return
            self._exportar_pdf_relatorio_atual(conteudo, titulo)
        except Exception as e:
            self._log_terminal(f"ERRO ao exportar PDF do popup: {e}", "ERRO")
            messagebox.showerror("Erro", f"Erro ao exportar PDF: {e}")
            traceback.print_exc()

    def _carregar_logs(self):
        """Carrega os logs e extrai todas as informacoes diretamente"""
        try:
            self._log_terminal("=" * 50, "DESTAQUE")
            self._log_terminal("INICIANDO CARREGAMENTO DE LOGS", "DESTAQUE")
            self._log_terminal("=" * 50, "DESTAQUE")

            if hasattr(self, "text_saida"):
                self.text_saida.delete(1.0, END)

            self._escrever_saida(
                "Sistema de Seguranca - Modulo de Relatorios\n", "titulo"
            )
            self._escrever_saida("=" * 70 + "\n", "titulo")
            self._escrever_saida(
                f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n", "info"
            )
            self._escrever_saida("A carregar logs...\n", "info")
            self._escrever_saida("=" * 70 + "\n\n", "titulo")

            self._log_terminal("Inicializando sistema...", "INFO")

            estado = EstadoDoSistema()
            inicializar(estado)

            self._log_terminal(f"Lendo logs da pasta: {PASTA_LOGS}", "INFO")

            self.eventos = ler_logs_pasta()

            self._log_terminal(
                f"Total de eventos carregados: {len(self.eventos)}", "SUCESSO"
            )

            if estado_sistema is not None:
                estado_sistema.events = self.eventos

            self.eventos_carregados = True

            if self.eventos:
                self._log_terminal("Iniciando extracao de dados...", "INFO")
                dados_extraidos = self._extrair_dados_dos_logs(self.eventos)
                self.dados["modulos"] = dados_extraidos["modulos"]
                self.dados["utilizadores"] = dados_extraidos["utilizadores"]
                self.dados["critical"] = dados_extraidos["critical"]
                self.dados["warning"] = dados_extraidos["warning"]
                self.dados["info"] = dados_extraidos["info"]
                self.dados["total_eventos"] = len(self.eventos)
                self._log_terminal("Dados extraidos com sucesso!", "SUCESSO")
            else:
                self._log_terminal("Nenhum evento encontrado!", "AVISO")
                self._escrever_saida(
                    "Nenhum evento encontrado nos logs.\n", "warning"
                )
                self._escrever_saida(f"Verifique a pasta: {PASTA_LOGS}\n", "warning")

            self._atualizar_resumo()

            if self.eventos:
                total = len(self.eventos)
                self._atualizar_status(f"{total} eventos carregados", "sucesso")
                self._log_terminal(
                    f"Sistema pronto! {total} eventos carregados", "SUCESSO"
                )
            else:
                self._atualizar_status("Nenhum evento encontrado", "aviso")

            self._log_terminal("=" * 50, "DESTAQUE")
            self._log_terminal("CARREGAMENTO CONCLUIDO", "SUCESSO")
            self._log_terminal("=" * 50, "DESTAQUE")

        except Exception as e:
            self._log_terminal(f"ERRO ao carregar logs: {e}", "ERRO")
            self._atualizar_status("Erro ao carregar", "erro")
            self._escrever_saida(f"Erro ao carregar logs: {e}\n", "error")
            traceback.print_exc()

    def _atualizar_resumo(self):
        """Atualiza o resumo na area de saida"""
        try:
            if not self.eventos:
                self._escrever_saida("Nenhum evento disponivel\n", "warning")
                return

            total_eventos = self.dados["total_eventos"]
            critical = self.dados["critical"]
            warning = self.dados["warning"]
            info = self.dados["info"]

            self._escrever_saida("RESUMO DO SISTEMA\n", "titulo")
            self._escrever_saida("-" * 70 + "\n", "titulo")
            self._escrever_saida(f"   Total Eventos:   {total_eventos}\n", "info")
            self._escrever_saida(
                f"   Criticos:        {critical}\n", "error" if critical > 0 else "info"
            )
            self._escrever_saida(
                f"   Avisos:          {warning}\n", "warning" if warning > 0 else "info"
            )
            self._escrever_saida(f"   Informacao:      {info}\n", "info")
            self._escrever_saida("-" * 70 + "\n", "titulo")

            self._escrever_saida("\n" + "=" * 70 + "\n", "titulo")
            self._escrever_saida("Sistema pronto para consultas!\n", "success")
            self._escrever_saida("=" * 70 + "\n", "titulo")

        except Exception as e:
            self._escrever_saida(f"Erro ao atualizar resumo: {e}\n", "error")
            traceback.print_exc()

    def _criar_interface(self):
        """Cria a interface com layout estruturado"""
        self.container = Frame(self.root, bg=self.cores["bg_principal"])
        self.container.pack(fill=BOTH, expand=True, padx=30, pady=20)

        self._criar_cabecalho()
        self._criar_area_conteudo()

    def _criar_cabecalho(self):
        """Cria o cabecalho"""
        cabecalho = Frame(self.container, bg=self.cores["bg_principal"])
        cabecalho.pack(fill=X, pady=(0, 15))

        Label(
            cabecalho,
            text="RELATORIOS DO SISTEMA",
            font=self.fontes["titulo"],
            fg=self.cores["texto_principal"],
            bg=self.cores["bg_principal"],
        ).pack(side=LEFT)

        status_frame = Frame(cabecalho, bg=self.cores["bg_principal"])
        status_frame.pack(side=RIGHT)

        self.status_label = Label(
            status_frame,
            text="A carregar...",
            font=self.fontes["status"],
            fg=self.cores["texto_aviso"],
            bg=self.cores["bg_principal"],
        )
        self.status_label.pack(side=RIGHT)

    def _criar_area_conteudo(self):
        """Cria a area de conteudo"""
        self.conteudo_frame = Frame(self.container, bg=self.cores["bg_principal"])
        self.conteudo_frame.pack(fill=BOTH, expand=True)

        self._criar_botoes()
        self._criar_saida()

    def _criar_botoes(self):
        """Cria os botoes de consulta"""
        botoes_frame = Frame(self.conteudo_frame, bg=self.cores["bg_principal"])
        botoes_frame.pack(fill=X, pady=(0, 20))

        botoes = [
            ("Consultar Sistema", self._popup_consulta),
            ("Detalhar Eventos", self._popup_detalhes),
            ("Relatorio Analitico", self._popup_analitico),
            ("Relatorio Utilizadores", self._popup_utilizadores),
            ("Debug", self._popup_debug),
            ("Reler Logs", self._reler_logs),
        ]

        for i, (texto, comando) in enumerate(botoes):
            btn = Button(
                botoes_frame,
                text=texto,
                font=self.fontes["botao"],
                bg=self.cores["bg_botao"],
                fg="#ffffff",
                relief=FLAT,
                cursor="hand2",
                padx=15,
                pady=10,
                command=comando,
            )
            btn.grid(row=i // 3, column=i % 3, padx=6, pady=6, sticky="ew")

            def on_enter(e, b=btn):
                b.config(bg=self.cores["bg_botao_hover"])

            def on_leave(e, b=btn):
                b.config(bg=self.cores["bg_botao"])

            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

        for i in range(3):
            botoes_frame.grid_columnconfigure(i, weight=1)

    def _criar_saida(self):
        """Cria a area de saida"""
        saida_frame = Frame(self.conteudo_frame, bg=self.cores["bg_principal"])
        saida_frame.pack(fill=BOTH, expand=True)

        Label(
            saida_frame,
            text="Saida do Sistema",
            font=self.fontes["subtitulo"],
            fg=self.cores["texto_principal"],
            bg=self.cores["bg_principal"],
        ).pack(anchor="w", pady=(0, 5))

        self.text_saida = scrolledtext.ScrolledText(
            saida_frame,
            font=self.fontes["saida"],
            bg="#ffffff",
            fg="#000000",
            insertbackground="black",
            wrap=WORD,
            height=25,
        )
        self.text_saida.pack(fill=BOTH, expand=True)

        self.text_saida.tag_configure("success", foreground="#2a8a4a")
        self.text_saida.tag_configure("error", foreground="#cc3333")
        self.text_saida.tag_configure("warning", foreground="#cc8800")
        self.text_saida.tag_configure("info", foreground="#1a6c9a")
        self.text_saida.tag_configure(
            "titulo", foreground="#1a6c8a", font=("Consolas", 11, "bold")
        )
        self.text_saida.tag_configure(
            "subtitulo", foreground="#1a2a4a", font=("Consolas", 10, "bold")
        )

    def _escrever_saida(self, texto, tag=None):
        """Escreve na area de saida"""
        if not hasattr(self, "text_saida") or self.text_saida is None:
            return

        if tag:
            self.text_saida.insert(END, texto, tag)
        else:
            self.text_saida.insert(END, texto)

        self.text_saida.see(END)
        self.root.update_idletasks()

    def _atualizar_status(self, mensagem, cor="sucesso"):
        """Atualiza o status"""
        cores = {
            "sucesso": self.cores["texto_sucesso"],
            "erro": self.cores["texto_perigo"],
            "aviso": self.cores["texto_aviso"],
        }
        self.status_label.config(
            text=mensagem, fg=cores.get(cor, self.cores["texto_sucesso"])
        )

    # ============================================================
    # METODO ADICIONAR BOTOES DE EXPORTACAO (ATUALIZADO COM CONFIG)
    # ============================================================

    def _adicionar_botoes_exportacao(
        self, popup, text_widget, tipo="popup", titulo="Relatorio"
    ):
        """
        Adiciona botoes de exportacao para um popup especifico.
        A configuracao de quais botoes aparecem e controlada por EXPORT_CONFIG.
        """
        config = obter_export_config(tipo)
        
        frame = Frame(popup, bg="#e8edf5")
        frame.pack(fill=X, pady=10, padx=10)

        Label(
            frame,
            text="Exportar:",
            font=self.fontes["subtitulo"],
            fg=self.cores["texto_principal"],
            bg="#e8edf5",
        ).pack(side=LEFT, padx=10)

        # Botao PDF - visivel conforme configuracao
        if config.get("pdf", True):
            def gerar_pdf():
                if tipo == "geral":
                    self._exportar_pdf_geral()
                else:
                    self._exportar_pdf_popup(text_widget, titulo)

            Button(
                frame,
                text="Gerar PDF",
                font=self.fontes["botao"],
                bg=self.cores["bg_botao"],
                fg="#ffffff",
                relief=FLAT,
                cursor="hand2",
                padx=15,
                pady=5,
                command=gerar_pdf,
            ).pack(side=LEFT, padx=5)

        # Botao CSV - visivel conforme configuracao
        if config.get("csv", True):
            def gerar_csv():
                if tipo == "geral":
                    self._exportar_csv_geral()
                else:
                    self._exportar_csv_popup(text_widget, titulo)

            Button(
                frame,
                text="Gerar CSV",
                font=self.fontes["botao"],
                bg=self.cores["bg_botao"],
                fg="#ffffff",
                relief=FLAT,
                cursor="hand2",
                padx=15,
                pady=5,
                command=gerar_csv,
            ).pack(side=LEFT, padx=5)

        Button(
            frame,
            text="Fechar",
            font=self.fontes["botao"],
            bg="#cc4444",
            fg="#ffffff",
            relief=FLAT,
            cursor="hand2",
            padx=15,
            pady=5,
            command=popup.destroy,
        ).pack(side=RIGHT, padx=10)

    # ============================================================
    # POPUPS
    # ============================================================

    def _criar_popup(self, titulo, width=900, height=650):
        """Cria um popup"""
        popup = Toplevel(self.root)
        popup.title(titulo)
        popup.geometry(f"{width}x{height}")
        popup.minsize(700, 500)
        popup.configure(bg="#e8edf5")
        popup.transient(self.root)
        popup.grab_set()

        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (width // 2)
        y = (popup.winfo_screenheight() // 2) - (height // 2)
        popup.geometry(f"{width}x{height}+{x}+{y}")

        return popup

    # ============================================================
    # POPUPS - CONSULTAS
    # ============================================================

    def _popup_consulta(self):
        """Popup consulta"""
        popup = self._criar_popup("Consulta ao Sistema")

        Label(
            popup,
            text="CONSULTA AO SISTEMA",
            font=self.fontes["popup_titulo"],
            fg=self.cores["texto_destaque"],
            bg="#e8edf5",
        ).pack(pady=15)

        text = scrolledtext.ScrolledText(
            popup,
            font=self.fontes["saida"],
            bg="#ffffff",
            fg="#000000",
            wrap=WORD,
            height=20,
        )
        text.pack(fill=BOTH, expand=True, padx=15, pady=10)

        text.tag_configure("success", foreground="#2a8a4a")
        text.tag_configure("error", foreground="#cc3333")
        text.tag_configure("warning", foreground="#cc8800")
        text.tag_configure("info", foreground="#1a6c9a")
        text.tag_configure(
            "titulo", foreground="#1a6c8a", font=("Consolas", 12, "bold")
        )
        text.tag_configure(
            "subtitulo", foreground="#1a2a4a", font=("Consolas", 11, "bold")
        )

        def executar():
            try:
                self._log_terminal("Executando consulta ao sistema...", "INFO")
                if estado_sistema and not estado_sistema.events and self.eventos:
                    estado_sistema.events = self.eventos

                f = io.StringIO()
                with redirect_stdout(f):
                    consultar_sistema()
                resultado = f.getvalue()

                # Insere o resultado e armazena para exportacao
                text.insert(END, resultado)
                self.ultimo_relatorio = resultado
                self.ultimo_titulo = "CONSULTA AO SISTEMA"

                text.config(state=DISABLED)
                self._log_terminal("Consulta concluida!", "SUCESSO")
            except Exception as e:
                self._log_terminal(f"ERRO na consulta: {e}", "ERRO")
                text.insert(END, f"\nErro: {e}\n", "error")
                text.config(state=DISABLED)
                traceback.print_exc()

        threading.Thread(target=executar, daemon=True).start()
        self._adicionar_botoes_exportacao(
            popup, text, "geral", "CONSULTA AO SISTEMA"
        )

    def _popup_detalhes(self):
        """Popup detalhes"""
        popup = self._criar_popup("Detalhamento de Eventos", width=1100, height=750)

        Label(
            popup,
            text="DETALHAMENTO DE EVENTOS POR MODULO",
            font=self.fontes["popup_titulo"],
            fg=self.cores["texto_destaque"],
            bg="#e8edf5",
        ).pack(pady=15)

        text_frame = Frame(popup, bg="#e8edf5")
        text_frame.pack(fill=BOTH, expand=True, padx=15, pady=10)

        text = scrolledtext.ScrolledText(
            text_frame,
            font=self.fontes["saida"],
            bg="#ffffff",
            fg="#000000",
            wrap=WORD,
            height=20,
        )
        text.pack(fill=BOTH, expand=True)

        text.tag_configure("success", foreground="#2a8a4a")
        text.tag_configure("error", foreground="#cc3333")
        text.tag_configure("warning", foreground="#cc8800")
        text.tag_configure("info", foreground="#1a6c9a")
        text.tag_configure(
            "titulo", foreground="#1a6c8a", font=("Consolas", 12, "bold")
        )
        text.tag_configure(
            "subtitulo", foreground="#1a2a4a", font=("Consolas", 11, "bold")
        )

        def executar():
            try:
                self._log_terminal(
                    "Gerando detalhamento de eventos por modulo...", "INFO"
                )
                if estado_sistema:
                    if not estado_sistema.events and self.eventos:
                        estado_sistema.events = self.eventos

                f = io.StringIO()
                with redirect_stdout(f):
                    detalhar_eventos_por_modulo()
                resultado = f.getvalue()

                text.insert(END, resultado)
                self.ultimo_relatorio = resultado
                self.ultimo_titulo = "DETALHAMENTO DE EVENTOS POR MODULO"

                text.config(state=DISABLED)
                self._log_terminal("Detalhamento concluido!", "SUCESSO")

            except Exception as e:
                self._log_terminal(f"ERRO no detalhamento: {e}", "ERRO")
                text.insert(END, f"\nErro ao gerar detalhamento: {e}\n", "error")
                text.config(state=DISABLED)
                traceback.print_exc()

        threading.Thread(target=executar, daemon=True).start()
        self._adicionar_botoes_exportacao(
            popup, text, "detalhes", "DETALHAMENTO DE EVENTOS POR MODULO"
        )

    def _popup_analitico(self):
        """Popup relatorio analitico"""
        popup = self._criar_popup("Relatorio Analitico")

        Label(
            popup,
            text="RELATORIO ANALITICO",
            font=self.fontes["popup_titulo"],
            fg=self.cores["texto_destaque"],
            bg="#e8edf5",
        ).pack(pady=15)

        text = scrolledtext.ScrolledText(
            popup,
            font=self.fontes["saida"],
            bg="#ffffff",
            fg="#000000",
            wrap=WORD,
            height=20,
        )
        text.pack(fill=BOTH, expand=True, padx=15, pady=10)

        text.tag_configure("success", foreground="#2a8a4a")
        text.tag_configure("error", foreground="#cc3333")
        text.tag_configure("warning", foreground="#cc8800")
        text.tag_configure("info", foreground="#1a6c9a")
        text.tag_configure(
            "titulo", foreground="#1a6c8a", font=("Consolas", 12, "bold")
        )
        text.tag_configure(
            "subtitulo", foreground="#1a2a4a", font=("Consolas", 11, "bold")
        )

        def executar():
            try:
                self._log_terminal("Gerando relatorio analitico...", "INFO")
                if estado_sistema and not estado_sistema.events and self.eventos:
                    estado_sistema.events = self.eventos

                resultado = gerar_relatorio_analitico()
                text.insert(END, resultado)
                self.ultimo_relatorio = resultado
                self.ultimo_titulo = "RELATORIO ANALITICO"

                text.config(state=DISABLED)
                self._log_terminal("Relatorio analitico concluido!", "SUCESSO")
            except Exception as e:
                self._log_terminal(f"ERRO no relatorio analitico: {e}", "ERRO")
                text.insert(END, f"\nErro: {e}\n", "error")
                text.config(state=DISABLED)
                traceback.print_exc()

        threading.Thread(target=executar, daemon=True).start()
        # ALTERADO: usa tipo "analitico" que tem CSV=False
        self._adicionar_botoes_exportacao(
            popup, text, "analitico", "RELATORIO ANALITICO"
        )

    # ============================================================
    # POPUP UTILIZADORES - OTIMIZADO
    # ============================================================

    def _popup_utilizadores(self):
        """Popup relatorio de utilizadores com calendario e filtros de status"""
        popup = self._criar_popup(
            "Relatorio de Utilizadores", width=1100, height=750
        )

        Label(
            popup,
            text="RELATORIO DE UTILIZADORES",
            font=self.fontes["popup_titulo"],
            fg=self.cores["texto_destaque"],
            bg="#e8edf5",
        ).pack(pady=15)

        # FILTROS - DATA E STATUS
        filtro_frame = Frame(popup, bg="#e8edf5")
        filtro_frame.pack(fill=X, padx=20, pady=10)

        # Linha 1: Filtro de Data
        data_frame = Frame(filtro_frame, bg="#e8edf5")
        data_frame.pack(fill=X, pady=5)

        Label(
            data_frame,
            text="Filtrar por Data:",
            font=self.fontes["subtitulo"],
            fg=self.cores["texto_principal"],
            bg="#e8edf5",
        ).pack(side=LEFT, padx=(0, 10))

        Label(
            data_frame,
            text="De:",
            font=self.fontes["normal"],
            fg=self.cores["texto_secundario"],
            bg="#e8edf5",
        ).pack(side=LEFT, padx=(0, 5))

        if CALENDARIO_DISPONIVEL:
            self.cal_inicio = DateEntry(  # type: ignore
                data_frame,
                width=12,
                background="#1a5c8a",
                foreground="#ffffff",
                borderwidth=0,
                year=datetime.now().year,
                month=datetime.now().month,
                day=datetime.now().day - 7,
                locale="pt_PT",
                date_pattern="yyyy-mm-dd",
            )
            self.cal_inicio.pack(side=LEFT, padx=(0, 10))
        else:
            self.data_inicio = Entry(
                data_frame,
                font=self.fontes["normal"],
                bg="#ffffff",
                fg="#000000",
                insertbackground="black",
                width=12,
            )
            self.data_inicio.pack(side=LEFT, padx=(0, 10))
            self.data_inicio.insert(
                0, (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            )

        Label(
            data_frame,
            text="Ate:",
            font=self.fontes["normal"],
            fg=self.cores["texto_secundario"],
            bg="#e8edf5",
        ).pack(side=LEFT, padx=(0, 5))

        if CALENDARIO_DISPONIVEL:
            self.cal_fim = DateEntry(  # type: ignore
                data_frame,
                width=12,
                background="#1a5c8a",
                foreground="#ffffff",
                borderwidth=0,
                year=datetime.now().year,
                month=datetime.now().month,
                day=datetime.now().day,
                locale="pt_PT",
                date_pattern="yyyy-mm-dd",
            )
            self.cal_fim.pack(side=LEFT, padx=(0, 10))
        else:
            self.data_fim = Entry(
                data_frame,
                font=self.fontes["normal"],
                bg="#ffffff",
                fg="#000000",
                insertbackground="black",
                width=12,
            )
            self.data_fim.pack(side=LEFT, padx=(0, 10))
            self.data_fim.insert(0, datetime.now().strftime("%Y-%m-%d"))

        # Linha 2: Filtro de Status
        status_frame = Frame(filtro_frame, bg="#e8edf5")
        status_frame.pack(fill=X, pady=5)

        Label(
            status_frame,
            text="Status:",
            font=self.fontes["subtitulo"],
            fg=self.cores["texto_principal"],
            bg="#e8edf5",
        ).pack(side=LEFT, padx=(0, 10))

        status_opcoes = [
            ("Todos", "todos"),
            ("Ativos", "ativos"),
            ("Desativados", "desativados"),
            ("Excluidos", "excluidos"),
        ]

        for texto, valor in status_opcoes:
            Radiobutton(
                status_frame,
                text=texto,
                variable=self.filtro_status,
                value=valor,
                font=self.fontes["normal"],
                fg=self.cores["texto_principal"],
                bg="#e8edf5",
                selectcolor="#d0e0f0",
            ).pack(side=LEFT, padx=5)

        # Linha 3: Botoes
        botoes_filtro_frame = Frame(filtro_frame, bg="#e8edf5")
        botoes_filtro_frame.pack(fill=X, pady=10)

        btn_filtrar = Button(
            botoes_filtro_frame,
            text="Aplicar Filtro",
            font=self.fontes["botao"],
            bg=self.cores["bg_botao"],
            fg="#ffffff",
            relief=FLAT,
            cursor="hand2",
            padx=15,
            pady=5,
            command=lambda: self._processar_utilizadores_com_filtro(
                popup, text, progress, bar
            ),
        )
        btn_filtrar.pack(side=LEFT, padx=5)

        btn_limpar = Button(
            botoes_filtro_frame,
            text="Ultimos 30 dias",
            font=self.fontes["botao"],
            bg=self.cores["bg_botao"],
            fg="#ffffff",
            relief=FLAT,
            cursor="hand2",
            padx=15,
            pady=5,
            command=lambda: self._limpar_filtro(popup, text, progress, bar),
        )
        btn_limpar.pack(side=LEFT, padx=5)

        # Progresso
        progress_frame = Frame(popup, bg="#e8edf5")
        progress_frame.pack(fill=X, padx=20, pady=5)

        progress = Label(
            progress_frame,
            text="Selecione um periodo e status, clique em 'Aplicar Filtro'",
            font=self.fontes["normal"],
            fg=self.cores["texto_aviso"],
            bg="#e8edf5",
        )
        progress.pack()

        bar = ttk.Progressbar(progress_frame, mode="indeterminate", length=400)
        bar.pack(pady=5)

        # Area de texto
        text = scrolledtext.ScrolledText(
            popup,
            font=self.fontes["saida"],
            bg="#ffffff",
            fg="#000000",
            wrap=WORD,
            height=20,
        )
        text.pack(fill=BOTH, expand=True, padx=15, pady=10)

        text.tag_configure("success", foreground="#2a8a4a")
        text.tag_configure("error", foreground="#cc3333")
        text.tag_configure("warning", foreground="#cc8800")
        text.tag_configure("info", foreground="#1a6c9a")
        text.tag_configure(
            "titulo", foreground="#1a6c8a", font=("Consolas", 11, "bold")
        )
        text.tag_configure(
            "subtitulo", foreground="#1a2a4a", font=("Consolas", 10, "bold")
        )

        # Adiciona botoes de exportacao para utilizadores
        self._adicionar_botoes_exportacao(
            popup, text, "utilizadores", "RELATORIO DE UTILIZADORES"
        )

    def _obter_datas_filtro(self):
        """Obtem as datas do filtro"""
        if CALENDARIO_DISPONIVEL:
            data_inicio = self.cal_inicio.get_date()
            data_fim = self.cal_fim.get_date()
            data_inicio = datetime.combine(data_inicio, datetime.min.time())
            data_fim = datetime.combine(data_fim, datetime.max.time())
            self._log_terminal(f"Datas obtidas: {data_inicio} a {data_fim}", "INFO")
            return data_inicio, data_fim
        else:
            try:
                data_inicio = datetime.strptime(
                    self.data_inicio.get().strip(), "%Y-%m-%d"
                )
                data_fim = datetime.strptime(self.data_fim.get().strip(), "%Y-%m-%d")
                data_fim = data_fim.replace(hour=23, minute=59, second=59)
                self._log_terminal(f"Datas obtidas: {data_inicio} a {data_fim}", "INFO")
                return data_inicio, data_fim
            except ValueError:
                return None, None

    def _processar_utilizadores_com_filtro(
        self, popup, text_area, progress_label, progress_bar
    ):
        """Processa o relatorio de utilizadores com filtro de data e status"""
        self._log_terminal("=" * 50, "DESTAQUE")
        self._log_terminal("INICIANDO FILTRO DE UTILIZADORES", "DESTAQUE")
        self._log_terminal("=" * 50, "DESTAQUE")

        data_inicio, data_fim = self._obter_datas_filtro()

        if data_inicio is None:
            self._log_terminal("ERRO: Formato de data invalido!", "ERRO")
            messagebox.showerror("Erro", "Formato de data invalido! Use YYYY-MM-DD")
            return

        if data_inicio > data_fim:  # type: ignore
            self._log_terminal("ERRO: Data inicial maior que data final!", "ERRO")
            messagebox.showerror(
                "Erro", "Data inicial nao pode ser maior que a data final!"
            )
            return

        status_selecionado = self.filtro_status.get()
        status_texto = {
            "todos": "Todos",
            "ativos": "ATIVOS",
            "desativados": "DESATIVADOS",
            "excluidos": "EXCLUIDOS",
        }

        self._log_terminal(f"Filtro aplicado:", "INFO")
        self._log_terminal(
            f"  - Periodo: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}",  # type: ignore
            "INFO",
        )
        self._log_terminal(
            f"  - Status: {status_texto.get(status_selecionado, 'Todos')}", "INFO"
        )

        # LIMPA A AREA DE TEXTO ANTES DE PROCESSAR
        text_area.delete(1.0, END)
        text_area.config(state=NORMAL)

        progress_bar.start(10)
        progress_label.config(
            text="A processar dados...", fg=self.cores["texto_aviso"]
        )

        def processar():
            try:
                self._log_terminal("Filtrando eventos por data...", "INFO")

                # Obtem eventos do estado_sistema ou local
                if estado_sistema and estado_sistema.events:
                    eventos = estado_sistema.events
                else:
                    eventos = self.eventos

                self._log_terminal(
                    f"Total de eventos disponiveis: {len(eventos)}", "INFO"
                )

                # Filtra eventos por data
                eventos_filtrados = []
                for evento in eventos:
                    timestamp = self._get_timestamp(evento)
                    if isinstance(timestamp, datetime):
                        if data_inicio <= timestamp <= data_fim:  # type: ignore
                            eventos_filtrados.append(evento)
                    else:
                        try:
                            ts_dt = (
                                datetime.fromtimestamp(timestamp)
                                if isinstance(timestamp, (int, float))
                                else timestamp
                            )
                            if data_inicio <= ts_dt <= data_fim:  # type: ignore
                                eventos_filtrados.append(evento)
                        except:
                            pass

                self._log_terminal(
                    f"Eventos filtrados por data: {len(eventos_filtrados)}", "SUCESSO"
                )

                if not eventos_filtrados:
                    text_area.delete(1.0, END)
                    text_area.insert(
                        END,
                        "\nNenhum evento encontrado no periodo selecionado.\n",
                        "warning",
                    )
                    text_area.config(state=DISABLED)
                    progress_bar.stop()
                    progress_label.config(
                        text="Nenhum evento no periodo", fg=self.cores["texto_aviso"]
                    )
                    return

                # Extrai utilizadores dos eventos filtrados
                utilizadores = self._extrair_utilizadores_dos_eventos(eventos_filtrados)

                if not utilizadores:
                    text_area.delete(1.0, END)
                    text_area.insert(
                        END,
                        "\nNenhum utilizador encontrado no periodo selecionado.\n",
                        "warning",
                    )
                    text_area.config(state=DISABLED)
                    progress_bar.stop()
                    progress_label.config(
                        text="Nenhum utilizador encontrado",
                        fg=self.cores["texto_aviso"],
                    )
                    return

                # Exibe o relatorio com o filtro de status
                titulo = f"RELATORIO DE UTILIZADORES - {status_texto.get(status_selecionado, 'Todos')}"
                self._exibir_relatorio_utilizadores(
                    text_area,
                    utilizadores,
                    status_selecionado,
                    titulo,
                    len(eventos_filtrados),
                )

                progress_bar.stop()
                progress_label.config(
                    text=f"{len(utilizadores)} utilizadores encontrados | {len(eventos_filtrados)} eventos",
                    fg=self.cores["texto_sucesso"],
                )
                text_area.config(state=DISABLED)

                self._log_terminal(
                    f"Processamento concluido! {len(utilizadores)} utilizadores",
                    "SUCESSO",
                )
                self._log_terminal("=" * 50, "DESTAQUE")

            except Exception as e:
                self._log_terminal(f"ERRO no processamento: {e}", "ERRO")
                progress_bar.stop()
                progress_label.config(
                    text=f"Erro: {str(e)[:50]}", fg=self.cores["texto_perigo"]
                )
                text_area.delete(1.0, END)
                text_area.insert(END, f"\nErro ao processar: {e}\n", "error")
                text_area.config(state=DISABLED)
                traceback.print_exc()

        threading.Thread(target=processar, daemon=True).start()

    def _limpar_filtro(self, popup, text_area, progress_label, progress_bar):
        """Limpa o filtro e mostra ultimos 30 dias"""
        self._log_terminal("Aplicando filtro: Ultimos 30 dias", "INFO")

        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(days=30)

        if CALENDARIO_DISPONIVEL:
            self.cal_inicio.set_date(data_inicio)
            self.cal_fim.set_date(data_fim)
        else:
            self.data_inicio.delete(0, END)
            self.data_inicio.insert(0, data_inicio.strftime("%Y-%m-%d"))
            self.data_fim.delete(0, END)
            self.data_fim.insert(0, data_fim.strftime("%Y-%m-%d"))

        self.filtro_status.set("todos")
        text_area.delete(1.0, END)
        self._processar_utilizadores_com_filtro(
            popup, text_area, progress_label, progress_bar
        )

    def _popup_debug(self):
        """Popup debug"""
        popup = self._criar_popup("Debug")

        Label(
            popup,
            text="DEBUG DO SISTEMA",
            font=self.fontes["popup_titulo"],
            fg=self.cores["texto_destaque"],
            bg="#e8edf5",
        ).pack(pady=15)

        text = scrolledtext.ScrolledText(
            popup,
            font=self.fontes["saida"],
            bg="#ffffff",
            fg="#000000",
            wrap=WORD,
            height=20,
        )
        text.pack(fill=BOTH, expand=True, padx=15, pady=10)

        text.tag_configure("success", foreground="#2a8a4a")
        text.tag_configure("error", foreground="#cc3333")
        text.tag_configure("warning", foreground="#cc8800")
        text.tag_configure("info", foreground="#1a6c9a")
        text.tag_configure(
            "titulo", foreground="#1a6c8a", font=("Consolas", 12, "bold")
        )
        text.tag_configure(
            "subtitulo", foreground="#1a2a4a", font=("Consolas", 11, "bold")
        )

        def executar():
            try:
                self._log_terminal("Executando debug...", "INFO")
                if estado_sistema and not estado_sistema.events and self.eventos:
                    estado_sistema.events = self.eventos

                f = io.StringIO()
                with redirect_stdout(f):
                    debug_logs()
                resultado = f.getvalue()
                text.insert(END, resultado)
                self.ultimo_relatorio = resultado
                self.ultimo_titulo = "DEBUG DO SISTEMA"

                text.config(state=DISABLED)
                self._log_terminal("Debug concluido!", "SUCESSO")
            except Exception as e:
                self._log_terminal(f"ERRO no debug: {e}", "ERRO")
                text.insert(END, f"\nErro: {e}\n", "error")
                text.config(state=DISABLED)
                traceback.print_exc()

        threading.Thread(target=executar, daemon=True).start()
        self._adicionar_botoes_exportacao(popup, text, "debug", "DEBUG DO SISTEMA")

    def _reler_logs(self):
        """Reler logs"""
        self._log_terminal("=" * 50, "DESTAQUE")
        self._log_terminal("RELENDO LOGS", "DESTAQUE")
        self._log_terminal("=" * 50, "DESTAQUE")

        self._escrever_saida("\nRELENDO LOGS...\n", "titulo")

        try:
            self.eventos = ler_logs_pasta()
            self._log_terminal(
                f"Total de eventos recarregados: {len(self.eventos)}", "SUCESSO"
            )

            if estado_sistema and self.eventos:
                estado_sistema.events = self.eventos

            if self.eventos:
                self._log_terminal("Re-extraindo dados...", "INFO")
                dados_extraidos = self._extrair_dados_dos_logs(self.eventos)
                self.dados["modulos"] = dados_extraidos["modulos"]
                self.dados["utilizadores"] = dados_extraidos["utilizadores"]
                self.dados["critical"] = dados_extraidos["critical"]
                self.dados["warning"] = dados_extraidos["warning"]
                self.dados["info"] = dados_extraidos["info"]
                self.dados["total_eventos"] = len(self.eventos)

            self._atualizar_resumo()

            self._atualizar_status("Logs recarregados", "sucesso")
            self._escrever_saida(
                f"\n{len(self.eventos)} logs recarregados com sucesso!\n", "success"
            )
            self._log_terminal(
                f"Logs recarregados com sucesso! {len(self.eventos)} eventos",
                "SUCESSO",
            )
            messagebox.showinfo(
                "Sucesso", f"{len(self.eventos)} logs recarregados com sucesso!"
            )
        except Exception as e:
            self._log_terminal(f"ERRO ao recarregar logs: {e}", "ERRO")
            self._escrever_saida(f"\nErro: {e}\n", "error")
            self._atualizar_status("Erro ao recarregar", "erro")
            traceback.print_exc()

    def executar(self):
        self.root.mainloop()


# ============================================================
# MAIN
# ============================================================


def main():
    app = InterfaceRelatorios()
    app.executar()


if __name__ == "__main__":
    main()