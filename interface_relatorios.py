# interface_relatorios.py
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from tkinter import *  # type: ignore
from tkinter import ttk, scrolledtext, messagebox, simpledialog
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

EXPORT_CONFIG = {
    "geral": {"pdf": True, "csv": True},
    "analitico": {"pdf": True, "csv": False},
    "detalhes": {"pdf": True, "csv": True},
    "utilizadores": {"pdf": True, "csv": True},
    "debug": {"pdf": True, "csv": False},
    "popup": {"pdf": True, "csv": True},
}


def obter_export_config(tipo_relatorio):
    return EXPORT_CONFIG.get(tipo_relatorio, {"pdf": True, "csv": True})


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
# CLASSE BASE PARA RELATORIOS
# ============================================================


class RelatorioBase:
    """Classe base para todos os relatorios - fornece o molde estetico"""

    def __init__(self, parent, text_widget, titulo="Relatorio"):
        self.parent = parent
        self.text_widget = text_widget
        self.titulo = titulo
        self.tipo = "popup"
        self.conteudo = None

    def executar(self):
        """Metodo principal que deve ser sobrescrito pelas classes filhas"""
        raise NotImplementedError("Subclasses devem implementar executar()")

    def obter_conteudo(self):
        """Obtem o conteudo do text_widget"""
        if self.conteudo is None:
            self.conteudo = self.text_widget.get(1.0, END)
        return self.conteudo

    def exportar_pdf(self):
        """Exporta o conteudo para PDF usando o molde estetico"""
        try:
            conteudo = self.obter_conteudo()
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum conteudo para exportar!")
                return
            self.parent._exportar_pdf_com_molde(conteudo, self.titulo, self.tipo)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar PDF: {e}")
            traceback.print_exc()

    def exportar_csv(self):
        """Exporta o conteudo para CSV - pode ser sobrescrito pelas filhas"""
        try:
            self.parent._exportar_csv_popup(self.text_widget, self.titulo)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")

    def criar_popup(self, width=900, height=650):
        """Cria a janela popup"""
        popup = Toplevel(self.parent.root)
        popup.title(self.titulo)
        popup.geometry(f"{width}x{height}")
        popup.minsize(700, 500)
        popup.configure(bg="#e8edf5")
        popup.transient(self.parent.root)
        popup.grab_set()

        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (width // 2)
        y = (popup.winfo_screenheight() // 2) - (height // 2)
        popup.geometry(f"{width}x{height}+{x}+{y}")

        return popup

    def configurar_texto(self, text_widget):
        """Configura as tags do texto"""
        text_widget.tag_configure("success", foreground="#2a8a4a")
        text_widget.tag_configure("error", foreground="#cc3333")
        text_widget.tag_configure("warning", foreground="#cc8800")
        text_widget.tag_configure("info", foreground="#1a6c9a")
        text_widget.tag_configure(
            "titulo", foreground="#1a6c8a", font=("Consolas", 12, "bold")
        )
        text_widget.tag_configure(
            "subtitulo", foreground="#1a2a4a", font=("Consolas", 11, "bold")
        )

    def configurar_botoes(self, popup):
        """Configura os botoes de exportacao no popup"""
        config = obter_export_config(self.tipo)

        frame = Frame(popup, bg="#e8edf5")
        frame.pack(fill=X, pady=10, padx=10)

        Label(
            frame,
            text="Exportar:",
            font=self.parent.fontes["subtitulo"],
            fg=self.parent.cores["texto_principal"],
            bg="#e8edf5",
        ).pack(side=LEFT, padx=10)

        if config.get("pdf", True):
            Button(
                frame,
                text="Gerar PDF",
                font=self.parent.fontes["botao"],
                bg=self.parent.cores["bg_botao"],
                fg="#ffffff",
                relief=FLAT,
                cursor="hand2",
                padx=15,
                pady=5,
                command=self.exportar_pdf,
            ).pack(side=LEFT, padx=5)

        if config.get("csv", True):
            Button(
                frame,
                text="Gerar CSV",
                font=self.parent.fontes["botao"],
                bg=self.parent.cores["bg_botao"],
                fg="#ffffff",
                relief=FLAT,
                cursor="hand2",
                padx=15,
                pady=5,
                command=self.exportar_csv,
            ).pack(side=LEFT, padx=5)

        Button(
            frame,
            text="Fechar",
            font=self.parent.fontes["botao"],
            bg="#cc4444",
            fg="#ffffff",
            relief=FLAT,
            cursor="hand2",
            padx=15,
            pady=5,
            command=popup.destroy,
        ).pack(side=RIGHT, padx=10)

    def executar_thread(self, target):
        """Executa uma funcao em uma thread"""
        threading.Thread(target=target, daemon=True).start()


# ============================================================
# CLASSE PARA CONSULTAR SISTEMA
# ============================================================


class RelatorioConsulta(RelatorioBase):
    """Relatorio de consulta ao sistema com CSV personalizado"""

    def __init__(self, parent, text_widget):
        super().__init__(parent, text_widget, "CONSULTA AO SISTEMA")
        self.tipo = "geral"

    def executar(self):
        """Executa a consulta ao sistema"""
        try:
            self.parent._log_terminal("Executando consulta ao sistema...", "INFO")

            if estado_sistema and not estado_sistema.events and self.parent.eventos:
                estado_sistema.events = self.parent.eventos

            f = io.StringIO()
            with redirect_stdout(f):
                consultar_sistema()
            resultado = f.getvalue()

            self.text_widget.insert(END, resultado)
            self.conteudo = resultado
            self.parent.ultimo_relatorio = resultado
            self.parent.ultimo_titulo = self.titulo

            self.text_widget.config(state=DISABLED)
            self.parent._log_terminal("Consulta concluida!", "SUCESSO")

        except Exception as e:
            self.parent._log_terminal(f"ERRO na consulta: {e}", "ERRO")
            self.text_widget.insert(END, f"\nErro: {e}\n", "error")
            self.text_widget.config(state=DISABLED)
            traceback.print_exc()

    def exportar_csv(self): # type: ignore
        """Exporta CSV com os dados gerais dos eventos"""
        try:
            self.parent._log_terminal("Iniciando exportacao CSV geral...", "INFO")

            if not self.parent.eventos:
                messagebox.showerror("Erro", "Nenhum evento carregado!")
                return None

            if estado_sistema and estado_sistema.events:
                eventos = estado_sistema.events
            else:
                eventos = self.parent.eventos

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"csv_todos_eventos_{timestamp}.csv"
            caminho = PASTA_RELATORIOS / nome_arquivo

            dados_exportar = []
            for idx, evento in enumerate(eventos, 1):
                payload = self.parent._get_payload(evento)
                timestamp_evento = self.parent._get_timestamp(evento)

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

            self.parent._log_terminal(
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
            self.parent._log_terminal(f"ERRO ao exportar CSV geral: {e}", "ERRO")
            messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")
            traceback.print_exc()
            return None


# ============================================================
# CLASSE PARA DETALHAR EVENTOS
# ============================================================


class RelatorioDetalhes(RelatorioBase):
    """Relatorio de detalhamento de eventos por modulo com CSV por modulo"""

    def __init__(self, parent, text_widget):
        super().__init__(parent, text_widget, "DETALHAMENTO DE EVENTOS POR MODULO")
        self.tipo = "detalhes"
        self.modulos_encontrados = {}

    def executar(self):
        """Executa o detalhamento de eventos"""
        try:
            self.parent._log_terminal(
                "Gerando detalhamento de eventos por modulo...", "INFO"
            )

            if estado_sistema:
                if not estado_sistema.events and self.parent.eventos:
                    estado_sistema.events = self.parent.eventos

            f = io.StringIO()
            with redirect_stdout(f):
                detalhar_eventos_por_modulo()
            resultado = f.getvalue()

            # Extrai os modulos DIRETAMENTE DOS EVENTOS (logs)
            self._extrair_modulos_dos_eventos()

            self.text_widget.insert(END, resultado)
            self.conteudo = resultado
            self.parent.ultimo_relatorio = resultado
            self.parent.ultimo_titulo = self.titulo

            self.text_widget.config(state=DISABLED)
            self.parent._log_terminal("Detalhamento concluido!", "SUCESSO")

        except Exception as e:
            self.parent._log_terminal(f"ERRO no detalhamento: {e}", "ERRO")
            self.text_widget.insert(
                END, f"\nErro ao gerar detalhamento: {e}\n", "error"
            )
            self.text_widget.config(state=DISABLED)
            traceback.print_exc()

    def _extrair_modulos_dos_eventos(self):
        """Extrai os modulos DIRETAMENTE dos eventos (logs)"""
        self.modulos_encontrados = {}

        if estado_sistema and estado_sistema.events:
            eventos = estado_sistema.events
        else:
            eventos = self.parent.eventos

        if not eventos:
            self.parent._log_terminal(
                "Nenhum evento disponivel para extrair modulos", "AVISO"
            )
            return

        self.parent._log_terminal(
            f"Extraindo modulos de {len(eventos)} eventos...", "INFO"
        )

        contagem_modulos = {}

        for evento in eventos:
            payload = self.parent._get_payload(evento)
            if payload:
                modulo = payload.get("modulo", "").upper()
                if modulo:
                    contagem_modulos[modulo] = contagem_modulos.get(modulo, 0) + 1

        modulos_ordenados = sorted(
            contagem_modulos.items(), key=lambda x: x[1], reverse=True
        )

        for idx, (nome_modulo, quantidade) in enumerate(modulos_ordenados, 1):
            self.modulos_encontrados[idx] = {"nome": nome_modulo, "eventos": quantidade}
            self.parent._log_terminal(
                f"  {idx}. {nome_modulo}: {quantidade} eventos", "INFO"
            )

        self.parent._log_terminal(
            f"Total de modulos encontrados: {len(self.modulos_encontrados)}", "SUCESSO"
        )

    def exportar_csv(self):
        """Exporta CSV com os dados do modulo selecionado"""
        try:
            self.parent._log_terminal("Iniciando exportacao CSV por modulo...", "INFO")

            if not self.modulos_encontrados:
                self._extrair_modulos_dos_eventos()

            if not self.modulos_encontrados:
                messagebox.showerror("Erro", "Nenhum modulo encontrado para exportar!")
                return None

            if estado_sistema and estado_sistema.events:
                eventos = estado_sistema.events
            else:
                eventos = self.parent.eventos

            if not eventos:
                messagebox.showerror("Erro", "Nenhum evento carregado!")
                return None

            lista_modulos = "MODULOS ENCONTRADOS:\n"
            for num, dados in self.modulos_encontrados.items():
                lista_modulos += (
                    f"   {num}. {dados['nome']}: {dados['eventos']} eventos\n"
                )

            modulo_num = simpledialog.askinteger(
                "Selecionar Modulo",
                f"{lista_modulos}\nDigite o numero do modulo para exportar:",
                minvalue=1,
                maxvalue=len(self.modulos_encontrados),
            )

            if modulo_num is None:
                self.parent._log_terminal("Exportacao cancelada pelo usuario", "INFO")
                return None

            if modulo_num not in self.modulos_encontrados:
                messagebox.showerror("Erro", "Numero de modulo invalido!")
                return None

            modulo_selecionado = self.modulos_encontrados[modulo_num]["nome"]
            self.parent._log_terminal(
                f"Modulo selecionado: {modulo_selecionado}", "INFO"
            )

            eventos_filtrados = []
            for evento in eventos:
                payload = self.parent._get_payload(evento)
                if payload:
                    modulo_evento = payload.get("modulo", "").upper()
                    if modulo_evento == modulo_selecionado:
                        eventos_filtrados.append(evento)

            if not eventos_filtrados:
                messagebox.showerror(
                    "Erro",
                    f"Nenhum evento encontrado para o modulo {modulo_selecionado}!",
                )
                return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"csv_{modulo_selecionado}_{timestamp}.csv"
            caminho = PASTA_RELATORIOS / nome_arquivo

            dados_exportar = []
            for idx, evento in enumerate(eventos_filtrados, 1):
                payload = self.parent._get_payload(evento)
                timestamp_evento = self.parent._get_timestamp(evento)

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

            self.parent._log_terminal(
                f"CSV do modulo {modulo_selecionado} gerado com sucesso: {caminho.name}",
                "SUCESSO",
            )

            try:
                os.startfile(str(caminho))
            except:
                pass

            messagebox.showinfo(
                "Sucesso",
                f"CSV exportado com sucesso!\n\n"
                f"Arquivo: {caminho.name}\n"
                f"Modulo: {modulo_selecionado}\n"
                f"Eventos: {len(dados_exportar)}\n"
                f"Local: {caminho}",
            )
            return str(caminho)

        except Exception as e:
            self.parent._log_terminal(f"ERRO ao exportar CSV por modulo: {e}", "ERRO")
            messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")
            traceback.print_exc()
            return None


# ============================================================
# CLASSE PARA RELATORIO ANALITICO
# ============================================================


class RelatorioAnalitico(RelatorioBase):
    """Relatorio analitico - apenas PDF, sem CSV"""

    def __init__(self, parent, text_widget):
        super().__init__(parent, text_widget, "RELATORIO ANALITICO")
        self.tipo = "analitico"

    def executar(self):
        """Executa o relatorio analitico"""
        try:
            self.parent._log_terminal("Gerando relatorio analitico...", "INFO")

            if estado_sistema and not estado_sistema.events and self.parent.eventos:
                estado_sistema.events = self.parent.eventos

            resultado = gerar_relatorio_analitico()

            self.text_widget.insert(END, resultado)
            self.conteudo = resultado
            self.parent.ultimo_relatorio = resultado
            self.parent.ultimo_titulo = self.titulo

            self.text_widget.config(state=DISABLED)
            self.parent._log_terminal("Relatorio analitico concluido!", "SUCESSO")

        except Exception as e:
            self.parent._log_terminal(f"ERRO no relatorio analitico: {e}", "ERRO")
            self.text_widget.insert(END, f"\nErro: {e}\n", "error")
            self.text_widget.config(state=DISABLED)
            traceback.print_exc()


# ============================================================
# CLASSE PARA RELATORIO DE UTILIZADORES
# ============================================================


class RelatorioUtilizadores(RelatorioBase):
    """Relatorio de utilizadores com filtro de status"""

    def __init__(self, parent, text_widget):
        super().__init__(parent, text_widget, "RELATORIO DE UTILIZADORES")
        self.tipo = "utilizadores"
        self.utilizadores_extraidos = {}
        self.filtro_status = StringVar(value="todos")
        self.conteudo_atual = ""

    def executar(self):
        """Executa o relatorio de utilizadores"""
        self.parent._log_terminal("=" * 50, "DESTAQUE")
        self.parent._log_terminal("CARREGANDO UTILIZADORES", "DESTAQUE")
        self.parent._log_terminal("=" * 50, "DESTAQUE")

        self.popup = self.criar_popup(width=1100, height=750)

        Label(
            self.popup,
            text="RELATORIO DE UTILIZADORES",
            font=self.parent.fontes["popup_titulo"],
            fg=self.parent.cores["texto_destaque"],
            bg="#e8edf5",
        ).pack(pady=15)

        filtro_frame = Frame(self.popup, bg="#e8edf5")
        filtro_frame.pack(fill=X, padx=20, pady=10)

        status_frame = Frame(filtro_frame, bg="#e8edf5")
        status_frame.pack(fill=X, pady=5)

        Label(
            status_frame,
            text="Status:",
            font=self.parent.fontes["subtitulo"],
            fg=self.parent.cores["texto_principal"],
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
                font=self.parent.fontes["normal"],
                fg=self.parent.cores["texto_principal"],
                bg="#e8edf5",
                selectcolor="#d0e0f0",
            ).pack(side=LEFT, padx=5)

        botoes_filtro_frame = Frame(filtro_frame, bg="#e8edf5")
        botoes_filtro_frame.pack(fill=X, pady=10)

        btn_filtrar = Button(
            botoes_filtro_frame,
            text="Aplicar Filtro",
            font=self.parent.fontes["botao"],
            bg=self.parent.cores["bg_botao"],
            fg="#ffffff",
            relief=FLAT,
            cursor="hand2",
            padx=15,
            pady=5,
            command=self.aplicar_filtro,
        )
        btn_filtrar.pack(side=LEFT, padx=5)

        self.text_widget = scrolledtext.ScrolledText(
            self.popup,
            font=self.parent.fontes["saida"],
            bg="#ffffff",
            fg="#000000",
            wrap=WORD,
            height=25,
        )
        self.text_widget.pack(fill=BOTH, expand=True, padx=15, pady=10)

        self.configurar_texto(self.text_widget)
        self.carregar_dados()
        self.configurar_botoes(self.popup)

    def obter_conteudo(self):
        self.conteudo_atual = self.text_widget.get(1.0, END)
        return self.conteudo_atual

    def carregar_dados(self):
        def carregar():
            try:
                if estado_sistema and estado_sistema.events:
                    eventos = estado_sistema.events
                else:
                    eventos = self.parent.eventos

                if not eventos:
                    self.text_widget.config(state=NORMAL)
                    self.text_widget.delete(1.0, END)
                    self.text_widget.insert(
                        END, "\nNenhum evento disponivel para analise.\n", "warning"
                    )
                    self.text_widget.config(state=DISABLED)
                    return

                utilizadores = self.parent._extrair_utilizadores_dos_eventos(eventos)
                self.utilizadores_extraidos = utilizadores

                if not utilizadores:
                    self.text_widget.config(state=NORMAL)
                    self.text_widget.delete(1.0, END)
                    self.text_widget.insert(
                        END, "\nNenhum utilizador encontrado nos logs.\n", "warning"
                    )
                    self.text_widget.config(state=DISABLED)
                    return

                titulo = "RELATORIO DE UTILIZADORES"
                self._exibir_relatorio(utilizadores, "todos", titulo, len(eventos))
                self.conteudo_atual = self.text_widget.get(1.0, END)

                self.parent._log_terminal(
                    f"Carregamento concluido! {len(utilizadores)} utilizadores",
                    "SUCESSO",
                )

            except Exception as e:
                self.parent._log_terminal(f"ERRO ao carregar utilizadores: {e}", "ERRO")
                self.text_widget.config(state=NORMAL)
                self.text_widget.delete(1.0, END)
                self.text_widget.insert(END, f"\nErro ao carregar: {e}\n", "error")
                self.text_widget.config(state=DISABLED)
                traceback.print_exc()

        threading.Thread(target=carregar, daemon=True).start()

    def aplicar_filtro(self):
        self.parent._log_terminal("=" * 50, "DESTAQUE")
        self.parent._log_terminal("FILTRANDO UTILIZADORES POR STATUS", "DESTAQUE")
        self.parent._log_terminal("=" * 50, "DESTAQUE")

        status_selecionado = self.filtro_status.get()
        status_texto = {
            "todos": "Todos",
            "ativos": "ATIVOS",
            "desativados": "DESATIVADOS",
            "excluidos": "EXCLUIDOS",
        }

        self.parent._log_terminal(
            f"  - Status selecionado: {status_texto.get(status_selecionado, 'Todos')}",
            "INFO",
        )

        def processar():
            try:
                if not self.utilizadores_extraidos:
                    self.carregar_dados()
                    return

                utilizadores = self.utilizadores_extraidos
                titulo = f"RELATORIO DE UTILIZADORES - {status_texto.get(status_selecionado, 'Todos')}"
                self._exibir_relatorio(
                    utilizadores,
                    status_selecionado,
                    titulo,
                    len(self.parent.eventos) if self.parent.eventos else 0,
                )
                self.conteudo_atual = self.text_widget.get(1.0, END)

                self.parent._log_terminal(
                    f"Processamento concluido! Filtro: {status_selecionado}", "SUCESSO"
                )
                self.parent._log_terminal("=" * 50, "DESTAQUE")

            except Exception as e:
                self.parent._log_terminal(f"ERRO no processamento: {e}", "ERRO")
                self.text_widget.config(state=NORMAL)
                self.text_widget.delete(1.0, END)
                self.text_widget.insert(END, f"\nErro ao processar: {e}\n", "error")
                self.text_widget.config(state=DISABLED)
                traceback.print_exc()

        threading.Thread(target=processar, daemon=True).start()

    def _exibir_relatorio(self, utilizadores, status_filtro, titulo, eventos_filtrados):
        self.text_widget.config(state=NORMAL)
        self.text_widget.delete(1.0, END)

        self.parent.ultimo_titulo = titulo

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

        todos_ativos = [
            u for u, d in utilizadores_filtrados.items() if d["status"] == "ATIVO"
        ]
        todos_desativados = [
            u for u, d in utilizadores_filtrados.items() if d["status"] == "DESATIVADO"
        ]
        todos_excluidos = [
            u for u, d in utilizadores_filtrados.items() if d["status"] == "EXCLUIDO"
        ]

        utilizadores_ordenados = sorted(
            utilizadores_filtrados.items(),
            key=lambda x: x[1]["total_eventos"],
            reverse=True,
        )

        total_filtrados = len(utilizadores_filtrados)
        total_ativos = len(todos_ativos)
        total_desativados = len(todos_desativados)
        total_excluidos = len(todos_excluidos)

        self.text_widget.insert(END, "\n" + "=" * 80 + "\n", "titulo")
        self.text_widget.insert(END, f"  {titulo}\n", "titulo")
        self.text_widget.insert(END, "=" * 80 + "\n", "titulo")
        self.text_widget.insert(END, "\n", "info")

        self.text_widget.insert(END, "RESUMO:\n", "subtitulo")

        status_label = self._get_status_label(status_filtro)
        self.text_widget.insert(
            END,
            f"   Total de utilizadores {status_label}: {total_filtrados}\n",
            "info",
        )

        if total_ativos > 0:
            self.text_widget.insert(END, f"   Ativos: {total_ativos}\n", "success")
        if total_desativados > 0:
            self.text_widget.insert(
                END, f"   Desativados: {total_desativados}\n", "warning"
            )
        if total_excluidos > 0:
            self.text_widget.insert(END, f"   Excluidos: {total_excluidos}\n", "error")

        self.text_widget.insert(
            END, f"\n   Eventos no periodo: {eventos_filtrados}\n", "info"
        )

        if status_filtro != "todos":
            status_nome = {
                "ativos": "ATIVOS",
                "desativados": "DESATIVADOS",
                "excluidos": "EXCLUIDOS",
            }.get(status_filtro, status_filtro.upper())
            self.text_widget.insert(
                END,
                f"\n   Filtro aplicado: Mostrando apenas {status_nome}\n",
                "info",
            )

        self.text_widget.insert(END, "\n" + "-" * 80 + "\n", "info")

        if utilizadores_ordenados:
            self.text_widget.insert(
                END,
                f"{'#':<4} | {'Utilizador':<20} | {'Status':<10} | {'Eventos':>8} | {'Ultimo Evento':<20} | {'Modulos':<15}\n",
                "titulo",
            )
            self.text_widget.insert(END, "-" * 80 + "\n", "info")

            for i, (utilizador, dados) in enumerate(utilizadores_ordenados, 1):
                status_icon = (
                    "[ATIVO]"
                    if dados["status"] == "ATIVO"
                    else (
                        "[DESATIVADO]"
                        if dados["status"] == "DESATIVADO"
                        else "[EXCLUIDO]"
                    )
                )
                ultimo = dados["ultimo_evento"].strftime("%Y-%m-%d %H:%M")
                modulos_str = ", ".join(list(dados["modulos"])[:3])
                if len(dados["modulos"]) > 3:
                    modulos_str += f" +{len(dados['modulos'])-3}"

                linha = f"{i:<4} | {utilizador[:20]:<20} | {status_icon} | {dados['total_eventos']:>8} | {ultimo:<20} | {modulos_str:<15}\n"
                self.text_widget.insert(END, linha, "info")
        else:
            self.text_widget.insert(
                END,
                "\n   Nenhum utilizador encontrado com o filtro selecionado.\n",
                "warning",
            )

        self.text_widget.insert(END, "\n" + "=" * 80 + "\n", "titulo")

        self.text_widget.insert(END, "\nLEGENDA:\n", "subtitulo")
        self.text_widget.insert(
            END,
            "   [ATIVO] - Utilizador que aparece nos logs (tem eventos registados)\n",
            "success",
        )
        self.text_widget.insert(
            END,
            "   [DESATIVADO] - Identificado por evento de desativacao no log\n",
            "warning",
        )
        self.text_widget.insert(
            END,
            "   [EXCLUIDO] - Identificado por evento de exclusao no log\n",
            "error",
        )
        self.text_widget.insert(END, "\n" + "=" * 80 + "\n", "titulo")

        self.parent.ultimo_relatorio = self.text_widget.get(1.0, END)
        self.text_widget.config(state=DISABLED)

    def _get_status_label(self, status_filtro):
        labels = {
            "todos": "identificados",
            "ativos": "ativos",
            "desativados": "desativados",
            "excluidos": "excluidos",
        }
        return labels.get(status_filtro, "identificados")


# ============================================================
# CLASSE PARA DEBUG
# ============================================================


class RelatorioDebug(RelatorioBase):
    """Relatorio de debug - apenas PDF, sem CSV"""

    def __init__(self, parent, text_widget):
        super().__init__(parent, text_widget, "DEBUG DO SISTEMA")
        self.tipo = "debug"

    def executar(self):
        """Executa o debug"""
        try:
            self.parent._log_terminal("Executando debug...", "INFO")

            if estado_sistema and not estado_sistema.events and self.parent.eventos:
                estado_sistema.events = self.parent.eventos

            f = io.StringIO()
            with redirect_stdout(f):
                debug_logs()
            resultado = f.getvalue()

            self.text_widget.insert(END, resultado)
            self.conteudo = resultado
            self.parent.ultimo_relatorio = resultado
            self.parent.ultimo_titulo = self.titulo

            self.text_widget.config(state=DISABLED)
            self.parent._log_terminal("Debug concluido!", "SUCESSO")

        except Exception as e:
            self.parent._log_terminal(f"ERRO no debug: {e}", "ERRO")
            self.text_widget.insert(END, f"\nErro: {e}\n", "error")
            self.text_widget.config(state=DISABLED)
            traceback.print_exc()


# ============================================================
# CLASSE PARA RELER LOGS
# ============================================================


class RelatorioRelerLogs:
    """Classe para recarregar os logs"""

    def __init__(self, parent):
        self.parent = parent

    def executar(self):
        """Recarrega os logs"""
        self.parent._log_terminal("=" * 50, "DESTAQUE")
        self.parent._log_terminal("RELENDO LOGS", "DESTAQUE")
        self.parent._log_terminal("=" * 50, "DESTAQUE")

        self.parent._escrever_saida("\nRELENDO LOGS...\n", "titulo")

        try:
            self.parent.eventos = ler_logs_pasta()
            self.parent._log_terminal(
                f"Total de eventos recarregados: {len(self.parent.eventos)}", "SUCESSO"
            )

            if estado_sistema and self.parent.eventos:
                estado_sistema.events = self.parent.eventos

            if self.parent.eventos:
                self.parent._log_terminal("Re-extraindo dados...", "INFO")
                dados_extraidos = self.parent._extrair_dados_dos_logs(
                    self.parent.eventos
                )
                self.parent.dados["modulos"] = dados_extraidos["modulos"]
                self.parent.dados["utilizadores"] = dados_extraidos["utilizadores"]
                self.parent.dados["critical"] = dados_extraidos["critical"]
                self.parent.dados["warning"] = dados_extraidos["warning"]
                self.parent.dados["info"] = dados_extraidos["info"]
                self.parent.dados["total_eventos"] = len(self.parent.eventos)
                self.parent.utilizadores_extraidos = {}

            self.parent._atualizar_resumo()

            self.parent._atualizar_status("Logs recarregados", "sucesso")
            self.parent._escrever_saida(
                f"\n{len(self.parent.eventos)} logs recarregados com sucesso!\n",
                "success",
            )
            self.parent._log_terminal(
                f"Logs recarregados com sucesso! {len(self.parent.eventos)} eventos",
                "SUCESSO",
            )
            messagebox.showinfo(
                "Sucesso", f"{len(self.parent.eventos)} logs recarregados com sucesso!"
            )
        except Exception as e:
            self.parent._log_terminal(f"ERRO ao recarregar logs: {e}", "ERRO")
            self.parent._escrever_saida(f"\nErro: {e}\n", "error")
            self.parent._atualizar_status("Erro ao recarregar", "erro")
            traceback.print_exc()


# ============================================================
# CLASSE PRINCIPAL
# ============================================================


class InterfaceRelatorios:
    def __init__(self, root=None):
        if root is None:
            self.root = Tk()
        else:
            self.root = root

        self.root.title("Sistema Integrado de Seguranca - Relatorios")
        self.root.geometry("1300x800")
        self.root.minsize(1100, 700)
        self.root.configure(bg="#e8edf5")

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
        self.utilizadores_extraidos = {}
        self.ultimo_relatorio = None
        self.ultimo_titulo = ""

        self._criar_interface()
        self.root.after(100, self._carregar_logs)

    def _log_terminal(self, mensagem, nivel="INFO"):
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

    def _get_payload(self, evento):
        if hasattr(evento, "payload"):
            return evento.payload
        elif isinstance(evento, tuple) and len(evento) >= 2:
            return evento[1]
        elif isinstance(evento, dict):
            return evento
        return None

    def _get_timestamp(self, evento):
        if hasattr(evento, "timestamp"):
            return evento.timestamp
        elif isinstance(evento, tuple) and len(evento) >= 3:
            return evento[2]
        return datetime.now()

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
        regex_acao_desativar = re.compile(
            r'(?:desativar|bloquear|suspender|inativar|desabilitar)\s+(?:utilizador|user|conta)\s+[\'"]?([a-zA-Z0-9_\-\.]+)',
            re.IGNORECASE,
        )
        regex_acao_excluir = re.compile(
            r'(?:excluir|remover|apagar|deletar|eliminar)\s+(?:utilizador|user|conta)\s+[\'"]?([a-zA-Z0-9_\-\.]+)',
            re.IGNORECASE,
        )

        for i, evento in enumerate(eventos):
            if i % 1000 == 0 and i > 0:
                self._log_terminal(
                    f"Progresso: {i}/{total_eventos} eventos processados", "INFO"
                )

            payload = self._get_payload(evento)
            if not payload:
                continue

            descricao = str(payload.get("descricao", ""))
            modulo = payload.get("modulo", "")
            evento_tipo = payload.get("tipo", "")

            utilizador = (
                payload.get("utilizador")
                or payload.get("username")
                or payload.get("user")
            )

            if not utilizador:
                user_match = regex_utilizador.search(descricao)
                if user_match:
                    utilizador = user_match.group(1)

            if not utilizador or utilizador == "Desconhecido":
                continue

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
                    "eventos_desativacao": 0,
                    "eventos_exclusao": 0,
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
            if evento_tipo:
                dados["tipos_eventos"].add(evento_tipo)

            descricao_lower = descricao.lower()

            acao_match = regex_acao_desativar.search(descricao_lower)
            if acao_match and acao_match.group(1).lower() == utilizador.lower():
                desativados.add(utilizador)
                dados["eventos_desativacao"] += 1
                if utilizador not in detalhes_desativacao:
                    quem_match = regex_quem.search(descricao)
                    detalhes_desativacao[utilizador] = {
                        "data_desativacao": timestamp,
                        "desativado_por": (
                            quem_match.group(1) if quem_match else "Sistema"
                        ),
                        "descricao": descricao[:100],
                        "modulo": modulo,
                    }
            elif regex_desativado.search(descricao_lower):
                user_in_desc = regex_utilizador.search(descricao)
                if user_in_desc and user_in_desc.group(1).lower() == utilizador.lower():
                    desativados.add(utilizador)
                    dados["eventos_desativacao"] += 1
                    if utilizador not in detalhes_desativacao:
                        quem_match = regex_quem.search(descricao)
                        detalhes_desativacao[utilizador] = {
                            "data_desativacao": timestamp,
                            "desativado_por": (
                                quem_match.group(1) if quem_match else "Sistema"
                            ),
                            "descricao": descricao[:100],
                            "modulo": modulo,
                        }

            acao_excluir_match = regex_acao_excluir.search(descricao_lower)
            if (
                acao_excluir_match
                and acao_excluir_match.group(1).lower() == utilizador.lower()
            ):
                excluidos.add(utilizador)
                dados["eventos_exclusao"] += 1
                if utilizador not in detalhes_exclusao:
                    quem_match = regex_quem.search(descricao)
                    detalhes_exclusao[utilizador] = {
                        "data_exclusao": timestamp,
                        "excluido_por": (
                            quem_match.group(1) if quem_match else "Sistema"
                        ),
                        "descricao": descricao[:100],
                        "modulo": modulo,
                    }
            elif regex_excluido.search(descricao_lower):
                user_in_desc = regex_utilizador.search(descricao)
                if user_in_desc and user_in_desc.group(1).lower() == utilizador.lower():
                    excluidos.add(utilizador)
                    dados["eventos_exclusao"] += 1
                    if utilizador not in detalhes_exclusao:
                        quem_match = regex_quem.search(descricao)
                        detalhes_exclusao[utilizador] = {
                            "data_exclusao": timestamp,
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

    def _extrair_dados_dos_logs(self, eventos):
        self._log_terminal("Iniciando extracao de dados dos logs...", "INFO")

        modulos = {}
        utilizadores = set()
        critical = 0
        warning = 0
        info = 0

        total_eventos = len(eventos)
        self._log_terminal(f"Processando {total_eventos} eventos...", "INFO")

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
            if i % 1000 == 0 and i > 0:
                self._log_terminal(
                    f"Progresso: {i}/{total_eventos} eventos processados", "INFO"
                )

            evento_str = str(evento).upper()
            evento_original = str(evento)

            mod_match = regex_modulo.search(evento_str)
            if mod_match:
                modulo = mod_match.group(1).upper()
                modulos[modulo] = modulos.get(modulo, 0) + 1

            user_match = regex_utilizador.search(evento_original)
            if user_match:
                utilizadores.add(user_match.group(1))

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

    def _exportar_csv_popup(self, text_widget, titulo="relatorio"):
        try:
            self._log_terminal("Iniciando exportacao CSV do popup...", "INFO")

            conteudo = text_widget.get(1.0, END)
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum conteudo para exportar!")
                return None

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

            linhas = conteudo.split("\n")
            dados_tabela = []
            cabecalho_encontrado = False
            cabecalho = []

            for linha in linhas:
                linha = linha.strip()

                if "|" in linha and "#" not in linha:
                    linha_clean = (
                        linha.replace("[ATIVO]", "")
                        .replace("[DESATIVADO]", "")
                        .replace("[EXCLUIDO]", "")
                        .strip()
                    )
                    partes = [p.strip() for p in linha_clean.split("|") if p.strip()]

                    if "Utilizador" in linha or "Status" in linha or "Eventos" in linha:
                        cabecalho = partes
                        cabecalho_encontrado = True
                        continue

                    if cabecalho_encontrado and len(partes) >= 3:
                        partes = [p.replace("●", "").strip() for p in partes]
                        dados_tabela.append(partes)

            if not dados_tabela:
                self._log_terminal(
                    "Nenhuma tabela encontrada, exportando como texto...", "INFO"
                )
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

            with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_ALL)
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
                for linha in dados_tabela:
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

    def _exportar_pdf_com_molde(self, conteudo, titulo, tipo="popup"):
        try:
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror(
                    "Erro",
                    "Nenhum relatorio para exportar! Execute uma consulta primeiro.",
                )
                return

            self._log_terminal(f"Iniciando exportacao PDF para: {titulo}", "INFO")

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
            nome_limpo = titulo.replace(" ", "_").replace("-", "_").lower()
            nome_limpo = re.sub(r"[^a-zA-Z0-9_]", "", nome_limpo)
            nome_pdf = f"{nome_limpo}_{timestamp}.pdf"
            caminho_pdf = PASTA_RELATORIOS / nome_pdf

            cor_primaria = HexColor("#1a5276")
            cor_secundaria = HexColor("#2980b9")
            cor_destaque = HexColor("#eaf2f8")
            cor_texto = HexColor("#1a2a4a")
            cor_texto_claro = HexColor("#5d6d7e")
            cor_borda = HexColor("#b0c4d8")
            cor_sucesso = HexColor("#27ae60")
            cor_alerta = HexColor("#f39c12")
            cor_perigo = HexColor("#e74c3c")
            cor_fundo_tabela = HexColor("#f8f9fa")
            cor_titulo_tabela = HexColor("#1a5276")

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
                fontSize=10,
                alignment=TA_LEFT,
                textColor=cor_secundaria,
                fontName="Helvetica-Bold",
                leading=16,
                leftIndent=20,
            )

            cabecalho_fundo = Drawing(720, 60)
            cabecalho_fundo.add(
                Rect(
                    0,
                    0,
                    720,
                    60,
                    fillColor=cor_destaque,
                    strokeColor=cor_primaria,
                    strokeWidth=1,
                )
            )
            story.append(cabecalho_fundo)
            story.append(Spacer(1, -55))

            story.append(
                Paragraph("SISTEMA INTEGRADO DE SEGURANCA", estilo_titulo_principal)
            )
            story.append(Paragraph("Relatorio de Auditoria", estilo_subtitulo))

            linha_decorativa = Drawing(720, 4)
            linha_decorativa.add(
                Line(150, 2, 570, 2, strokeColor=cor_primaria, strokeWidth=2)
            )
            story.append(linha_decorativa)
            story.append(Spacer(1, 8))

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

            linha_separadora = Drawing(720, 2)
            linha_separadora.add(
                Line(0, 1, 720, 1, strokeColor=cor_borda, strokeWidth=0.5)
            )
            story.append(linha_separadora)
            story.append(Spacer(1, 8))

            linhas = conteudo.split("\n")

            while linhas and not linhas[0].strip():
                linhas = linhas[1:]

            cabecalho_tabela = []
            dados_tabela = []
            tem_tabela = False

            for linha in linhas:
                if "|" in linha and (
                    "Utilizador" in linha or "Status" in linha or "Eventos" in linha
                ):
                    tem_tabela = True
                    break

            for linha in linhas:
                linha = linha.rstrip()

                if linha.strip().startswith("=") or linha.strip().startswith("-"):
                    if "----" not in linha and "====" not in linha:
                        story.append(Spacer(1, 3))
                    continue

                if "|" in linha and tem_tabela:
                    if "Utilizador" in linha or "Status" in linha or "Eventos" in linha:
                        linha_clean = (
                            linha.replace("[ATIVO]", "")
                            .replace("[DESATIVADO]", "")
                            .replace("[EXCLUIDO]", "")
                            .strip()
                        )
                        partes = [
                            p.strip() for p in linha_clean.split("|") if p.strip()
                        ]
                        if len(partes) >= 4:
                            cabecalho_tabela = partes
                            story.append(Spacer(1, 5))
                            story.append(Paragraph("DETALHES", estilo_titulo_secao))
                            story.append(Spacer(1, 3))
                        continue

                    if cabecalho_tabela:
                        linha_clean = (
                            linha.replace("[ATIVO]", "")
                            .replace("[DESATIVADO]", "")
                            .replace("[EXCLUIDO]", "")
                            .strip()
                        )
                        partes = [
                            p.strip() for p in linha_clean.split("|") if p.strip()
                        ]
                        if len(partes) >= 4:
                            while len(partes) < len(cabecalho_tabela):
                                partes.append("")
                            dados_tabela.append(partes)
                    continue

                linha_clean = linha.strip()

                if not linha_clean:
                    story.append(Spacer(1, 3))
                    continue

                if (
                    "RELATORIO" in linha_clean.upper()
                    or "CONSULTA" in linha_clean.upper()
                    or "DETALHAMENTO" in linha_clean.upper()
                ):
                    story.append(Paragraph(linha_clean, estilo_titulo_secao))
                    story.append(Spacer(1, 3))
                elif "RESUMO" in linha_clean.upper() and ":" in linha_clean:
                    story.append(Paragraph("RESUMO", estilo_titulo_secao))
                    story.append(Spacer(1, 3))
                elif "LEGENDA" in linha_clean.upper() and ":" in linha_clean:
                    story.append(Spacer(1, 5))
                    story.append(Paragraph("LEGENDA", estilo_titulo_secao))
                    story.append(Spacer(1, 3))
                elif "Total de" in linha_clean and "utilizadores" in linha_clean:
                    story.append(Paragraph(linha_clean, estilo_valor_destaque))
                    story.append(Spacer(1, 1))
                elif "Ativos:" in linha_clean and "[" not in linha_clean:
                    story.append(Paragraph(linha_clean, estilo_valor_destaque))
                    story.append(Spacer(1, 1))
                elif "Desativados:" in linha_clean and "[" not in linha_clean:
                    story.append(Paragraph(linha_clean, estilo_valor_destaque))
                    story.append(Spacer(1, 1))
                elif "Excluidos:" in linha_clean and "[" not in linha_clean:
                    story.append(Paragraph(linha_clean, estilo_valor_destaque))
                    story.append(Spacer(1, 1))
                elif "Eventos no periodo:" in linha_clean:
                    story.append(Paragraph(linha_clean, estilo_resumo))
                    story.append(Spacer(1, 1))
                elif "Filtro aplicado:" in linha_clean:
                    story.append(Paragraph(linha_clean, estilo_info))
                    story.append(Spacer(1, 2))
                elif (
                    "[ATIVO]" in linha_clean
                    or "[DESATIVADO]" in linha_clean
                    or "[EXCLUIDO]" in linha_clean
                ):
                    if "[ATIVO]" in linha_clean:
                        linha_formatada = linha_clean.replace("[ATIVO]", "● ATIVO")
                        story.append(Paragraph(linha_formatada, estilo_resumo))
                        story.append(Spacer(1, 1))
                    elif "[DESATIVADO]" in linha_clean:
                        linha_formatada = linha_clean.replace(
                            "[DESATIVADO]", "● DESATIVADO"
                        )
                        story.append(Paragraph(linha_formatada, estilo_resumo))
                        story.append(Spacer(1, 1))
                    elif "[EXCLUIDO]" in linha_clean:
                        linha_formatada = linha_clean.replace(
                            "[EXCLUIDO]", "● EXCLUIDO"
                        )
                        story.append(Paragraph(linha_formatada, estilo_resumo))
                        story.append(Spacer(1, 1))
                else:
                    if "|" in linha_clean:
                        continue
                    if len(linha_clean) > 200:
                        linha_clean = linha_clean[:197] + "..."
                    story.append(Paragraph(linha_clean, estilo_normal))
                    story.append(Spacer(1, 2))

            if cabecalho_tabela and dados_tabela:
                tabela_dados = [cabecalho_tabela]
                for linha in dados_tabela:
                    while len(linha) < len(cabecalho_tabela):
                        linha.append("")
                    tabela_dados.append(linha)

                col_widths = []
                for i in range(len(cabecalho_tabela)):
                    if i == 0:
                        col_widths.append(1.2 * cm)
                    elif i == 1:
                        col_widths.append(5 * cm)
                    elif i == 2:
                        col_widths.append(2.5 * cm)
                    elif i == 3:
                        col_widths.append(2.5 * cm)
                    elif i == 4:
                        col_widths.append(4.5 * cm)
                    else:
                        col_widths.append(4 * cm)

                col_widths = col_widths[: len(cabecalho_tabela)]

                if len(tabela_dados) > 30:
                    tabela_dados = tabela_dados[:30]
                    tabela_dados.append(["...", "...", "...", "...", "...", "..."])

                tabela = Table(tabela_dados, colWidths=col_widths)
                tabela.setStyle(
                    TableStyle(
                        [
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 8),
                            ("BACKGROUND", (0, 0), (-1, 0), cor_titulo_tabela),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 1), (-1, -1), 7),
                            ("BACKGROUND", (0, 1), (-1, -1), cor_fundo_tabela),
                            ("TEXTCOLOR", (0, 1), (-1, -1), cor_texto),
                            ("GRID", (0, 0), (-1, -1), 0.5, cor_borda),
                            ("ALIGN", (0, 0), (0, -1), "CENTER"),
                            ("ALIGN", (1, 0), (1, -1), "LEFT"),
                            ("ALIGN", (2, 0), (2, -1), "CENTER"),
                            ("ALIGN", (3, 0), (3, -1), "CENTER"),
                            ("ALIGN", (4, 0), (4, -1), "CENTER"),
                            ("ALIGN", (5, 0), (5, -1), "CENTER"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                for i in range(1, len(tabela_dados)):
                    if i % 2 == 0:
                        tabela.setStyle(
                            TableStyle(
                                [("BACKGROUND", (0, i), (-1, i), HexColor("#e8f4f8"))]
                            )
                        )
                story.append(tabela)

            story.append(Spacer(1, 15))

            linha_inferior = Drawing(720, 4)
            linha_inferior.add(
                Line(0, 2, 720, 2, strokeColor=cor_primaria, strokeWidth=1.5)
            )
            story.append(linha_inferior)
            story.append(Spacer(1, 6))

            story.append(
                Paragraph(
                    f"Relatório gerado automaticamente pelo Sistema Integrado de Segurança",
                    estilo_rodape,
                )
            )
            story.append(
                Paragraph(
                    f"Documento: REL-{datetime.now().strftime('%Y%m%d')}-{timestamp[-4:]} | Versão: 1.0",
                    estilo_rodape,
                )
            )
            story.append(
                Paragraph(
                    f"© {datetime.now().year} - Todos os direitos reservados",
                    estilo_rodape,
                )
            )

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
    # FUNCOES DE INTERFACE
    # ============================================================

    def _criar_interface(self):
        self.container = Frame(self.root, bg=self.cores["bg_principal"])
        self.container.pack(fill=BOTH, expand=True, padx=30, pady=20)

        self._criar_cabecalho()
        self._criar_area_conteudo()

    def _criar_cabecalho(self):
        cabecalho = Frame(self.container, bg=self.cores["bg_principal"])
        cabecalho.pack(fill=X, pady=(0, 15))

        Label(
            cabecalho,
            text="RELATÓRIOS DO SISTEMA",
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
        self.conteudo_frame = Frame(self.container, bg=self.cores["bg_principal"])
        self.conteudo_frame.pack(fill=BOTH, expand=True)

        self._criar_botoes()
        self._criar_saida()

    def _criar_botoes(self):
        botoes_frame = Frame(self.conteudo_frame, bg=self.cores["bg_principal"])
        botoes_frame.pack(fill=X, pady=(0, 20))

        botoes = [
            ("Consulta Geral Sistema", self._abrir_consulta),
            ("Detalhar Eventos por módulo", self._abrir_detalhes),
            ("Relatório Analítico", self._abrir_analitico),
            ("Relatório Utilizadores", self._abrir_utilizadores),
            ("Debug", self._abrir_debug),
            ("Reler Logs", self._abrir_reler_logs),
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
        saida_frame = Frame(self.conteudo_frame, bg=self.cores["bg_principal"])
        saida_frame.pack(fill=BOTH, expand=True)

        Label(
            saida_frame,
            text="Saída do Sistema",
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
        if not hasattr(self, "text_saida") or self.text_saida is None:
            return

        if tag:
            self.text_saida.insert(END, texto, tag)
        else:
            self.text_saida.insert(END, texto)

        self.text_saida.see(END)
        self.root.update_idletasks()

    def _atualizar_status(self, mensagem, cor="sucesso"):
        cores = {
            "sucesso": self.cores["texto_sucesso"],
            "erro": self.cores["texto_perigo"],
            "aviso": self.cores["texto_aviso"],
        }
        self.status_label.config(
            text=mensagem, fg=cores.get(cor, self.cores["texto_sucesso"])
        )

    def _carregar_logs(self):
        try:
            self._log_terminal("=" * 50, "DESTAQUE")
            self._log_terminal("INICIANDO CARREGAMENTO DE LOGS", "DESTAQUE")
            self._log_terminal("=" * 50, "DESTAQUE")

            if hasattr(self, "text_saida"):
                self.text_saida.delete(1.0, END)

            self._escrever_saida(
                "Sistema de Segurança - Módulo de Relatórios\n", "titulo"
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
                self._log_terminal("Iniciando extração de dados...", "INFO")
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
                self._escrever_saida("Nenhum evento encontrado nos logs.\n", "warning")
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

    # ============================================================
    # METODOS PARA ABRIR OS RELATORIOS
    # ============================================================

    def _abrir_consulta(self):
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

        self._configurar_tags_texto(text)

        relatorio = RelatorioConsulta(self, text)
        self._executar_relatorio(relatorio, popup)

    def _abrir_detalhes(self):
        popup = self._criar_popup("Detalhamento de Eventos", 1100, 750)

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

        self._configurar_tags_texto(text)

        relatorio = RelatorioDetalhes(self, text)
        self._executar_relatorio(relatorio, popup)

    def _abrir_analitico(self):
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

        self._configurar_tags_texto(text)

        relatorio = RelatorioAnalitico(self, text)
        self._executar_relatorio(relatorio, popup)

    def _abrir_utilizadores(self):
        text = scrolledtext.ScrolledText(
            self.root,
            font=self.fontes["saida"],
            bg="#ffffff",
            fg="#000000",
            wrap=WORD,
            height=25,
        )

        relatorio = RelatorioUtilizadores(self, text)
        relatorio.executar()

    def _abrir_debug(self):
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

        self._configurar_tags_texto(text)

        relatorio = RelatorioDebug(self, text)
        self._executar_relatorio(relatorio, popup)

    def _abrir_reler_logs(self):
        reler = RelatorioRelerLogs(self)
        reler.executar()

    def _criar_popup(self, titulo, width=900, height=650):
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

    def _configurar_tags_texto(self, text_widget):
        text_widget.tag_configure("success", foreground="#2a8a4a")
        text_widget.tag_configure("error", foreground="#cc3333")
        text_widget.tag_configure("warning", foreground="#cc8800")
        text_widget.tag_configure("info", foreground="#1a6c9a")
        text_widget.tag_configure(
            "titulo", foreground="#1a6c8a", font=("Consolas", 12, "bold")
        )
        text_widget.tag_configure(
            "subtitulo", foreground="#1a2a4a", font=("Consolas", 11, "bold")
        )

    def _executar_relatorio(self, relatorio, popup):
        def executar_thread():
            relatorio.executar()

        threading.Thread(target=executar_thread, daemon=True).start()
        relatorio.configurar_botoes(popup)

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
