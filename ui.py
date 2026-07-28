"""
ui.py - Interface gráfica principal
puxando informações do core.py e exportacao.py
"""

import os
import csv
import io
import re
import threading
import traceback
from collections import Counter
from pathlib import Path  # ← Usado para caminhos
from datetime import datetime
from tkinter import scrolledtext, messagebox, simpledialog
from contextlib import redirect_stdout

# ============================================================
# IMPORTAÇÕES DO TKINTER - ESPECÍFICAS
# ============================================================

from tkinter import (
    Tk,  # Janela principal
    Toplevel,  # Janelas popup/secundárias
    Frame,  # Container para organizar widgets
    Label,  # Texto estático
    Button,  # Botão clicável
    Radiobutton,  # Botões de rádio (seleção única)
    Canvas,  # Área rolável (usada no popup de seleção de módulo)
    StringVar,  # Variável para texto em Radiobutton
    END,  # Constante para final do texto
    WORD,  # Constante para quebra de palavra
    DISABLED,  # Estado desabilitado de widget
    NORMAL,  # Estado normal de widget
    FLAT,  # Estilo de relevo plano
    LEFT,  # Alinhamento à esquerda
    RIGHT,  # Alinhamento à direita
    X,  # Preenchimento horizontal
    Y,  # Preenchimento vertical
    BOTH,  # Preenchimento em ambos os eixos
)
from tkinter import ttk  # Treeview (tabela nativa) e Scrollbar

# Módulos adicionais do tkinter
from tkinter import scrolledtext  # Área de texto com scroll
from tkinter import messagebox  # Caixas de diálogo (alertas, erros)
from tkinter import simpledialog  # Caixas de diálogo com entrada

# ============================================================
# IMPORTAÇÕES DO core.py (CLASSE MÃE / BACKEND)
# ============================================================

from core import (
    PASTA_LOGS,
    PASTA_RELATORIOS,
    EstadoDoSistema,
    ler_logs_pasta,
    extrair_utilizadores_dos_eventos,
    extrair_estatisticas,
    consultar_sistema,
    detalhar_eventos_por_modulo,
    gerar_relatorio_analitico,
    debug_logs,
    inicializar,
    estado_sistema,
    ultima_leitura,
)

# ============================================================
# IMPORTAÇÕES DO exportacao.py (CLASSE FILHA / EXPORTAÇÃO)
# ============================================================

from exportacao import exportar_relatorio, ExportadorPDF, ExportadorCSV

# ============================================================
# CLASSES DE RELATORIOS (Interface) - IGUAL AO ORIGINAL
# ============================================================


class RelatorioBase:
    """Classe base para relatórios - IDÊNTICA ao original"""

    def __init__(self, parent, text_widget, titulo="Relatorio"):
        self.parent = parent
        self.text_widget = text_widget
        self.titulo = titulo
        self.tipo = "popup"
        self.conteudo = None
        self.popup = None

    def executar(self):
        raise NotImplementedError("Subclasses devem implementar executar()")

    def obter_conteudo(self):
        if self.conteudo is None:
            self.conteudo = self.text_widget.get(1.0, END)
        return self.conteudo

    def exportar_pdf(self):
        try:
            conteudo = self.obter_conteudo()
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum conteudo para exportar!")
                return None
            self.parent._exportar_pdf_com_molde(conteudo, self.titulo, self.tipo)
            return None
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar PDF: {e}")
            traceback.print_exc()
            return None

    def exportar_csv(self):
        try:
            self.parent._exportar_csv_popup(self.text_widget, self.titulo)
            return None
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")
            return None

    def criar_popup(self, width=900, height=650):
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
        self.popup = popup
        return popup

    def configurar_texto(self, text_widget):
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
        config = self.parent.obter_export_config(self.tipo)
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
        threading.Thread(target=target, daemon=True).start()


# ============================================================
# CLASSE: RelatorioConsulta - IGUAL AO ORIGINAL
# ============================================================


class RelatorioConsulta(RelatorioBase):
    def __init__(self, parent, text_widget):
        super().__init__(parent, text_widget, "CONSULTA AO SISTEMA")
        self.tipo = "geral"

    def executar(self):
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

    def exportar_pdf(self):
        """Exporta o PDF da consulta com formatação específica"""
        try:
            conteudo = self.obter_conteudo()
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum conteudo para exportar!")
                return
            self.parent._exportar_pdf_consulta(conteudo, self.titulo)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar PDF: {e}")
            traceback.print_exc()

    def exportar_csv(self):
        try:
            self.parent._log_terminal("Iniciando exportacao CSV geral...", "INFO")
            if estado_sistema and estado_sistema.events:
                eventos = estado_sistema.events
            else:
                eventos = self.parent.eventos
            if not eventos:
                messagebox.showerror("Erro", "Nenhum evento carregado!")
                return None
            separador = self.parent._popup_escolher_separador()
            if separador is None:
                self.parent._log_terminal(
                    "Exportacao CSV cancelada pelo usuario", "INFO"
                )
                return None
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
                status = (
                    "CRITICO"
                    if severidade == "CRITICAL"
                    else "ATENCAO" if severidade == "WARNING" else "INFO"
                )
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
                writer = csv.writer(f, delimiter=separador, quoting=csv.QUOTE_ALL)
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
                f"CSV exportado com sucesso!\n\nArquivo: {caminho.name}\nEventos: {len(dados_exportar)}\nLocal: {caminho}",
            )
            return None
        except Exception as e:
            self.parent._log_terminal(f"ERRO ao exportar CSV geral: {e}", "ERRO")
            messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")
            traceback.print_exc()
            return None


# ============================================================
# CLASSE: RelatorioDetalhes - IGUAL AO ORIGINAL
# ============================================================


class RelatorioDetalhes(RelatorioBase):
    def __init__(self, parent, text_widget=None):
        super().__init__(parent, None, "DETALHAMENTO DE EVENTOS POR MODULO")
        self.tipo = "detalhes"
        self.dados_modulos = {}
        self.total_eventos = 0
        self.modulo_selecionado_atual = None
        self.tree_eventos = None
        self.label_modulo_selecionado = None
        self.label_stats = None
        self.popup = None
        self.conteudo = None

    def executar(self):
        self.parent._log_terminal("=" * 50, "DESTAQUE")
        self.parent._log_terminal("GERANDO DETALHAMENTO POR MODULO", "DESTAQUE")
        self.parent._log_terminal("=" * 50, "DESTAQUE")
        self.popup = self.criar_popup(width=1100, height=720)
        Label(
            self.popup,
            text="DETALHAMENTO DE EVENTOS POR MODULO",
            font=self.parent.fontes["popup_titulo"],
            fg=self.parent.cores["texto_destaque"],
            bg="#e8edf5",
        ).pack(pady=(15, 10))

        # --- Cabecalho: modulo atual + botao para trocar ---
        cabecalho_frame = Frame(self.popup, bg="#e8edf5")
        cabecalho_frame.pack(fill=X, padx=20, pady=(0, 5))

        self.label_modulo_selecionado = Label(
            cabecalho_frame,
            text="A carregar...",
            font=self.parent.fontes["subtitulo"],
            fg=self.parent.cores["texto_principal"],
            bg="#e8edf5",
        )
        self.label_modulo_selecionado.pack(side=LEFT)

        Button(
            cabecalho_frame,
            text="🔁 Selecionar outro módulo",
            font=self.parent.fontes["normal"],
            bg=self.parent.cores["bg_botao_utilitario"],
            fg="#ffffff",
            relief=FLAT,
            cursor="hand2",
            padx=10,
            pady=4,
            command=self._selecionar_outro_modulo,
        ).pack(side=RIGHT)

        self.label_stats = Label(
            self.popup,
            text="",
            font=self.parent.fontes["normal"],
            fg=self.parent.cores["texto_secundario"],
            bg="#e8edf5",
            justify=LEFT,
        )
        self.label_stats.pack(anchor="w", padx=20, pady=(0, 8))

        # --- Tabela de eventos do modulo selecionado ---
        estilo = ttk.Style()
        estilo.configure("Detalhes.Treeview", font=("Consolas", 10), rowheight=24)
        estilo.configure(
            "Detalhes.Treeview.Heading", font=self.parent.fontes["botao"]
        )

        eventos_frame = Frame(self.popup, bg="#ffffff")
        eventos_frame.pack(fill=BOTH, expand=True, padx=15, pady=(0, 10))

        colunas_eventos = ("num", "hora", "tipo", "descricao", "utilizador", "severidade")
        titulos_eventos = {
            "num": "#",
            "hora": "Data/Hora",
            "tipo": "Tipo",
            "descricao": "Descricao",
            "utilizador": "Utilizador",
            "severidade": "Severidade",
        }
        larguras_eventos = {
            "num": 45,
            "hora": 130,
            "tipo": 110,
            "descricao": 320,
            "utilizador": 140,
            "severidade": 100,
        }

        self.tree_eventos = ttk.Treeview(
            eventos_frame,
            columns=colunas_eventos,
            show="headings",
            style="Detalhes.Treeview",
        )
        for col in colunas_eventos:
            self.tree_eventos.heading(col, text=titulos_eventos[col])
            self.tree_eventos.column(
                col,
                width=larguras_eventos[col],
                anchor="w" if col in ("descricao", "utilizador") else "center",
                stretch=(col == "descricao"),
            )
        self.tree_eventos.tag_configure(
            "CRITICAL", foreground=self.parent.cores["texto_perigo"]
        )
        self.tree_eventos.tag_configure(
            "WARNING", foreground=self.parent.cores["texto_aviso"]
        )
        self.tree_eventos.tag_configure(
            "INFO", foreground=self.parent.cores["texto_secundario"]
        )
        scroll_eventos = ttk.Scrollbar(
            eventos_frame, orient="vertical", command=self.tree_eventos.yview
        )
        self.tree_eventos.configure(yscrollcommand=scroll_eventos.set)
        self.tree_eventos.pack(side=LEFT, fill=BOTH, expand=True)
        scroll_eventos.pack(side=RIGHT, fill=Y)

        self.carregar_dados()
        self.configurar_botoes(self.popup)

    def obter_conteudo(self):
        if self.conteudo is None:
            self.conteudo = ""
        return self.conteudo

    def _coletar_dados(self):
        if estado_sistema and estado_sistema.events:
            eventos = estado_sistema.events
        else:
            eventos = self.parent.eventos

        dados_modulos = {}
        for evento in eventos:
            payload = self.parent._get_payload(evento)
            if not payload:
                continue
            modulo = (payload.get("modulo", "") or "GERAL").upper()
            timestamp_evento = self.parent._get_timestamp(evento) or datetime.now()
            severidade = payload.get("severidade", "INFO")

            if modulo not in dados_modulos:
                dados_modulos[modulo] = {
                    "eventos_lista": [],
                    "severidades": {"CRITICAL": 0, "WARNING": 0, "INFO": 0},
                    "utilizadores": set(),
                }
            info_modulo = dados_modulos[modulo]
            info_modulo["eventos_lista"].append(
                {
                    "timestamp": timestamp_evento,
                    "tipo": getattr(evento, "event_type", ""),
                    "descricao": payload.get("descricao", ""),
                    "utilizador": payload.get("utilizador", "") or "-",
                    "severidade": severidade,
                }
            )
            if severidade in info_modulo["severidades"]:
                info_modulo["severidades"][severidade] += 1
            if payload.get("utilizador"):
                info_modulo["utilizadores"].add(payload["utilizador"])

        return dados_modulos, len(eventos)

    def carregar_dados(self):
        """Coleta os dados numa thread separada (sem tocar em widgets) e so
        entao agenda qualquer atualizacao visual na thread principal via
        root.after - forma segura de mexer no Tkinter a partir de outra thread."""

        def carregar():
            try:
                dados_modulos, total_eventos = self._coletar_dados()
                self.dados_modulos = dados_modulos
                self.total_eventos = total_eventos
                if not dados_modulos:
                    self.parent.root.after(
                        0,
                        lambda: self._mostrar_aviso(
                            "Nenhum evento disponivel para analise."
                        ),
                    )
                    return
                self.parent.root.after(0, self._abrir_selecao_inicial)
                self.parent._log_terminal(
                    f"Dados carregados! {len(dados_modulos)} modulos encontrados",
                    "SUCESSO",
                )
            except Exception as e:
                self.parent._log_terminal(f"ERRO no detalhamento: {e}", "ERRO")
                erro_msg = str(e)
                self.parent.root.after(
                    0,
                    lambda: self._mostrar_aviso(
                        f"Erro ao gerar detalhamento: {erro_msg}", tag="error"
                    ),
                )
                traceback.print_exc()

        threading.Thread(target=carregar, daemon=True).start()

    def _mostrar_aviso(self, mensagem, tag="warning"):
        """Executa sempre na thread principal"""
        for item in self.tree_eventos.get_children():
            self.tree_eventos.delete(item)
        cor = (
            self.parent.cores["texto_perigo"]
            if tag == "error"
            else self.parent.cores["texto_aviso"]
        )
        self.label_modulo_selecionado.config(text=mensagem, fg=cor)
        self.label_stats.config(text="")
        self.conteudo = mensagem
        self.modulo_selecionado_atual = None

    def _abrir_selecao_inicial(self):
        """Executa na thread principal (agendado via root.after)"""
        modulo_escolhido = self._popup_escolher_modulo()
        if modulo_escolhido is None:
            self._mostrar_aviso("Nenhum modulo selecionado.")
            self.parent._log_terminal("Selecao de modulo cancelada", "INFO")
            return
        self._carregar_eventos_modulo(modulo_escolhido)

    def _selecionar_outro_modulo(self):
        modulo_escolhido = self._popup_escolher_modulo()
        if modulo_escolhido is None:
            return
        self._carregar_eventos_modulo(modulo_escolhido)

    def _popup_escolher_modulo(self):
        """Pop-up para escolher qual modulo sera exibido no relatorio.

        Retorna o nome do modulo escolhido, ou None se o usuario cancelar.
        """
        resultado = {"modulo": None}

        largura, altura = 380, 480
        janela_pai = self.popup if self.popup else self.parent.root
        popup = Toplevel(janela_pai)
        popup.title("Selecionar Módulo")
        popup.configure(bg=self.parent.cores["bg_principal"])
        popup.resizable(False, False)
        popup.transient(janela_pai)
        popup.grab_set()

        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (largura // 2)
        y = (popup.winfo_screenheight() // 2) - (altura // 2)
        popup.geometry(f"{largura}x{altura}+{x}+{y}")

        Label(
            popup,
            text="Selecione o módulo",
            font=self.parent.fontes["popup_titulo"],
            fg=self.parent.cores["texto_principal"],
            bg=self.parent.cores["bg_principal"],
        ).pack(pady=(18, 4))
        Label(
            popup,
            text="Os eventos do módulo escolhido serão exibidos no relatório",
            font=self.parent.fontes["normal"],
            fg=self.parent.cores["texto_secundario"],
            bg=self.parent.cores["bg_principal"],
            wraplength=320,
            justify=LEFT,
        ).pack(pady=(0, 12))

        lista_frame = Frame(popup, bg=self.parent.cores["bg_principal"])
        lista_frame.pack(fill=BOTH, expand=True, padx=20)

        canvas = Canvas(
            lista_frame, bg=self.parent.cores["bg_principal"], highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            lista_frame, orient="vertical", command=canvas.yview
        )
        botoes_frame = Frame(canvas, bg=self.parent.cores["bg_principal"])

        botoes_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=botoes_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        def escolher(nome_modulo):
            resultado["modulo"] = nome_modulo
            popup.destroy()

        modulos_ordenados = sorted(
            self.dados_modulos.items(),
            key=lambda x: len(x[1]["eventos_lista"]),
            reverse=True,
        )
        for nome_modulo, info in modulos_ordenados:
            quantidade = len(info["eventos_lista"])
            Button(
                botoes_frame,
                text=f"{nome_modulo}   ({quantidade} eventos)",
                font=self.parent.fontes["botao"],
                bg=self.parent.cores["bg_botao"],
                fg="#ffffff",
                activebackground=self.parent.cores["bg_botao_hover"],
                activeforeground="#ffffff",
                relief=FLAT,
                anchor="w",
                cursor="hand2",
                command=lambda n=nome_modulo: escolher(n),
            ).pack(fill=X, pady=4, padx=2)

        Button(
            popup,
            text="Cancelar",
            font=self.parent.fontes["normal"],
            bg=self.parent.cores["bg_principal"],
            fg=self.parent.cores["texto_secundario"],
            relief=FLAT,
            cursor="hand2",
            command=popup.destroy,
        ).pack(pady=12)

        popup.wait_window()
        return resultado["modulo"]

    def _carregar_eventos_modulo(self, modulo):
        self.modulo_selecionado_atual = modulo
        info = self.dados_modulos.get(modulo)
        if not info:
            return

        for item in self.tree_eventos.get_children():
            self.tree_eventos.delete(item)

        eventos_ordenados = sorted(
            info["eventos_lista"], key=lambda e: e["timestamp"], reverse=True
        )
        sev = info["severidades"]

        self.label_modulo_selecionado.config(
            text=f"Módulo: {modulo}", fg=self.parent.cores["texto_principal"]
        )
        self.label_stats.config(
            text=(
                f"Total: {len(eventos_ordenados)} eventos   |   "
                f"CRITICAL: {sev['CRITICAL']}   |   WARNING: {sev['WARNING']}   |   "
                f"INFO: {sev['INFO']}   |   Utilizadores envolvidos: {len(info['utilizadores'])}"
            )
        )

        for i, ev in enumerate(eventos_ordenados, 1):
            severidade = (
                ev["severidade"]
                if ev["severidade"] in ("CRITICAL", "WARNING", "INFO")
                else "INFO"
            )
            self.tree_eventos.insert(
                "",
                END,
                values=(
                    i,
                    ev["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                    ev["tipo"],
                    ev["descricao"],
                    ev["utilizador"],
                    severidade,
                ),
                tags=(severidade,),
            )

        # --- Texto equivalente, usado para exportar em PDF: SO deste modulo ---
        texto = []
        texto.append("=" * 80)
        texto.append(f"  MODULO: {modulo}")
        texto.append("=" * 80)
        texto.append("\nRESUMO:")
        texto.append(f"   Total de eventos: {len(eventos_ordenados)}")
        if sev["CRITICAL"] > 0:
            texto.append(f"   CRITICAL: {sev['CRITICAL']}")
        if sev["WARNING"] > 0:
            texto.append(f"   WARNING: {sev['WARNING']}")
        if sev["INFO"] > 0:
            texto.append(f"   INFO: {sev['INFO']}")
        texto.append(f"   Utilizadores envolvidos: {len(info['utilizadores'])}")
        texto.append("\n" + "-" * 80)
        texto.append(
            f"{'Data/Hora':<20} | {'Severidade':<10} | {'Utilizador':<20} | Descricao"
        )
        texto.append("-" * 80)
        for ev in eventos_ordenados:
            hora = ev["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            texto.append(
                f"{hora:<20} | {ev['severidade']:<10} | {ev['utilizador'][:20]:<20} | {ev['descricao']}"
            )
        texto.append("\n" + "=" * 80)

        self.conteudo = "\n".join(texto)
        self.parent.ultimo_relatorio = self.conteudo
        self.parent.ultimo_titulo = f"{self.titulo} - {modulo}"

    def exportar_csv(self):
        try:
            self.parent._log_terminal("Iniciando exportacao CSV por modulo...", "INFO")
            if not self.modulo_selecionado_atual or not self.dados_modulos.get(
                self.modulo_selecionado_atual
            ):
                messagebox.showerror(
                    "Erro", "Nenhum modulo selecionado para exportar!"
                )
                return None

            modulo_selecionado = self.modulo_selecionado_atual
            eventos_modulo = self.dados_modulos[modulo_selecionado]["eventos_lista"]
            if not eventos_modulo:
                messagebox.showerror(
                    "Erro",
                    f"Nenhum evento encontrado para o modulo {modulo_selecionado}!",
                )
                return None

            separador = self.parent._popup_escolher_separador()
            if separador is None:
                self.parent._log_terminal(
                    "Exportacao CSV cancelada pelo usuario", "INFO"
                )
                return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"csv_{modulo_selecionado}_{timestamp}.csv"
            caminho = PASTA_RELATORIOS / nome_arquivo

            dados_exportar = []
            for idx, ev in enumerate(eventos_modulo, 1):
                status = (
                    "CRITICO"
                    if ev["severidade"] == "CRITICAL"
                    else "ATENCAO" if ev["severidade"] == "WARNING" else "INFO"
                )
                dados_exportar.append(
                    [
                        idx,
                        ev["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                        status,
                        modulo_selecionado,
                        ev["descricao"][:200],
                        ev["utilizador"],
                    ]
                )

            with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=separador, quoting=csv.QUOTE_ALL)
                writer.writerow(
                    ["ID", "Data/Hora", "Status", "Modulo", "Observacao", "Utilizador"]
                )
                for linha in dados_exportar:
                    writer.writerow(linha)

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
                f"CSV exportado com sucesso!\n\nArquivo: {caminho.name}\nModulo: {modulo_selecionado}\nEventos: {len(dados_exportar)}\nLocal: {caminho}",
            )
            return None
        except Exception as e:
            self.parent._log_terminal(f"ERRO ao exportar CSV por modulo: {e}", "ERRO")
            messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")
            traceback.print_exc()
            return None

    def exportar_pdf(self):
        """Exporta o PDF apenas do modulo selecionado no momento"""
        try:
            if not self.modulo_selecionado_atual:
                messagebox.showerror(
                    "Erro", "Selecione um modulo antes de exportar o PDF!"
                )
                return
            conteudo = self.obter_conteudo()
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum conteudo para exportar!")
                return
            titulo_pdf = f"{self.titulo} - {self.modulo_selecionado_atual}"
            self.parent._exportar_pdf_detalhamento(conteudo, titulo_pdf)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar PDF: {e}")
            traceback.print_exc()

# ============================================================
# CLASSE: RelatorioAnalitico - IGUAL AO ORIGINAL
# ============================================================


class RelatorioAnalitico(RelatorioBase):
    def __init__(self, parent, text_widget):
        super().__init__(parent, text_widget, "RELATORIO ANALITICO")
        self.tipo = "analitico"

    def executar(self):
        try:
            self.parent._log_terminal("Gerando relatorio analitico...", "INFO")
            if estado_sistema and not estado_sistema.events and self.parent.eventos:
                estado_sistema.events = self.parent.eventos
            resultado = gerar_relatorio_analitico()
            self._inserir_com_destaque(resultado)
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

    def _inserir_com_destaque(self, texto):
        """Insere o relatorio linha a linha, destacando alertas e niveis de severidade.

        Preparado para quando o core.py passar a gerar linhas de alerta
        (ex: "[ALERTA] Modulo X concentra 40% dos eventos CRITICAL") -
        essas linhas ja aparecerao destacadas automaticamente, sem precisar
        mexer na interface de novo.
        """
        padrao_secao = re.compile(r"^\d+\.\s+[A-ZÀ-Ú]")
        for linha in texto.split("\n"):
            stripped = linha.strip()
            linha_upper = stripped.upper()
            if not stripped:
                self.text_widget.insert(END, "\n")
                continue
            if "[ALERTA]" in linha_upper or linha_upper.startswith("ALERTA"):
                self.text_widget.insert(END, linha + "\n", "alerta")
            elif stripped.startswith("=") or padrao_secao.match(stripped):
                self.text_widget.insert(END, linha + "\n", "titulo")
            elif "CRITICAL" in linha_upper:
                self.text_widget.insert(END, linha + "\n", "error")
            elif "WARNING" in linha_upper:
                self.text_widget.insert(END, linha + "\n", "warning")
            else:
                self.text_widget.insert(END, linha + "\n", "info")

    def exportar_pdf(self):
        """Exporta o PDF do Relatório Analítico com formatação exclusiva"""
        try:
            conteudo = self.obter_conteudo()
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum conteudo para exportar!")
                return
            self.parent._exportar_pdf_analitico(conteudo, self.titulo)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar PDF: {e}")
            traceback.print_exc()


# ============================================================
# CLASSE: RelatorioUtilizadores - IGUAL AO ORIGINAL
# ============================================================


class RelatorioUtilizadores(RelatorioBase):
    def __init__(self, parent, text_widget=None):
        super().__init__(parent, None, "RELATORIO DE UTILIZADORES")
        self.tipo = "utilizadores"
        self.utilizadores_extraidos = {}
        self.filtro_status = StringVar(value="todos")
        self.conteudo_atual = ""
        self.conteudo = None
        self.dados_tabela_atual = []
        self.tree = None
        self.resumo_frame = None
        self.popup = None

    def executar(self):
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

        # --- Resumo (contadores) acima da tabela ---
        self.resumo_frame = Frame(self.popup, bg="#e8edf5")
        self.resumo_frame.pack(fill=X, padx=20, pady=(0, 5))

        # --- Tabela real (Treeview) em vez de texto ASCII ---
        tabela_frame = Frame(self.popup, bg="#ffffff")
        tabela_frame.pack(fill=BOTH, expand=True, padx=15, pady=10)

        estilo = ttk.Style()
        estilo.configure(
            "Utilizadores.Treeview",
            font=("Consolas", 10),
            rowheight=24,
        )
        estilo.configure(
            "Utilizadores.Treeview.Heading",
            font=self.parent.fontes["botao"],
        )

        colunas = ("num", "utilizador", "status", "eventos", "ultimo_evento", "modulos")
        titulos = {
            "num": "#",
            "utilizador": "Utilizador",
            "status": "Status",
            "eventos": "Eventos",
            "ultimo_evento": "Ultimo Evento",
            "modulos": "Modulos",
        }
        larguras = {
            "num": 45,
            "utilizador": 170,
            "status": 120,
            "eventos": 80,
            "ultimo_evento": 140,
            "modulos": 260,
        }
        ancoras = {
            "num": "center",
            "utilizador": "w",
            "status": "center",
            "eventos": "center",
            "ultimo_evento": "center",
            "modulos": "w",
        }

        self.tree = ttk.Treeview(
            tabela_frame,
            columns=colunas,
            show="headings",
            style="Utilizadores.Treeview",
        )
        for col in colunas:
            self.tree.heading(col, text=titulos[col])
            self.tree.column(col, width=larguras[col], anchor=ancoras[col], stretch=(col == "modulos"))

        self.tree.tag_configure("ativo", foreground=self.parent.cores["texto_sucesso"])
        self.tree.tag_configure(
            "desativado", foreground=self.parent.cores["texto_aviso"]
        )
        self.tree.tag_configure("excluido", foreground=self.parent.cores["texto_perigo"])

        scroll_v = ttk.Scrollbar(tabela_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_v.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scroll_v.pack(side=RIGHT, fill=Y)
        self.tree.bind("<Double-1>", self._abrir_detalhe_utilizador)

        Label(
            self.popup,
            text="Dica: de dois cliques num utilizador para ver os detalhes completos",
            font=self.parent.fontes["status"],
            fg=self.parent.cores["texto_secundario"],
            bg="#e8edf5",
        ).pack(pady=(0, 5))

        self.carregar_dados()
        self.configurar_botoes(self.popup)

    def obter_conteudo(self):
        if self.conteudo is None:
            self.conteudo = self.conteudo_atual
        return self.conteudo

    def carregar_dados(self):
        def carregar():
            try:
                if estado_sistema and estado_sistema.events:
                    eventos = estado_sistema.events
                else:
                    eventos = self.parent.eventos
                if not eventos:
                    self._mostrar_aviso("Nenhum evento disponivel para analise.")
                    return
                utilizadores = self.parent._extrair_utilizadores_dos_eventos(eventos)
                self.utilizadores_extraidos = utilizadores
                if not utilizadores:
                    self._mostrar_aviso("Nenhum utilizador encontrado nos logs.")
                    return
                titulo = "RELATORIO DE UTILIZADORES"
                self._exibir_relatorio(utilizadores, "todos", titulo, len(eventos))
                self.parent._log_terminal(
                    f"Carregamento concluido! {len(utilizadores)} utilizadores",
                    "SUCESSO",
                )
            except Exception as e:
                self.parent._log_terminal(f"ERRO ao carregar utilizadores: {e}", "ERRO")
                self._mostrar_aviso(f"Erro ao carregar: {e}", tag="error")
                traceback.print_exc()

        threading.Thread(target=carregar, daemon=True).start()

    def _mostrar_aviso(self, mensagem, tag="warning"):
        """Mostra um aviso na area da tabela quando nao ha dados"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for widget in self.resumo_frame.winfo_children():
            widget.destroy()
        cor = (
            self.parent.cores["texto_perigo"]
            if tag == "error"
            else self.parent.cores["texto_aviso"]
        )
        Label(
            self.resumo_frame,
            text=mensagem,
            font=self.parent.fontes["normal"],
            fg=cor,
            bg="#e8edf5",
        ).pack(anchor="w")
        self.conteudo = mensagem
        self.dados_tabela_atual = []

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
                self.parent._log_terminal(
                    f"Processamento concluido! Filtro: {status_selecionado}", "SUCESSO"
                )
                self.parent._log_terminal("=" * 50, "DESTAQUE")
            except Exception as e:
                self.parent._log_terminal(f"ERRO no processamento: {e}", "ERRO")
                self._mostrar_aviso(f"Erro ao processar: {e}", tag="error")
                traceback.print_exc()

        threading.Thread(target=processar, daemon=True).start()

    def _exibir_relatorio(self, utilizadores, status_filtro, titulo, eventos_filtrados):
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

        total_ativos = sum(
            1 for d in utilizadores_filtrados.values() if d["status"] == "ATIVO"
        )
        total_desativados = sum(
            1 for d in utilizadores_filtrados.values() if d["status"] == "DESATIVADO"
        )
        total_excluidos = sum(
            1 for d in utilizadores_filtrados.values() if d["status"] == "EXCLUIDO"
        )
        total_filtrados = len(utilizadores_filtrados)

        utilizadores_ordenados = sorted(
            utilizadores_filtrados.items(),
            key=lambda x: x[1]["total_eventos"],
            reverse=True,
        )

        # --- Resumo (Labels coloridos, substitui o bloco de texto) ---
        for widget in self.resumo_frame.winfo_children():
            widget.destroy()

        status_label = self._get_status_label(status_filtro)
        Label(
            self.resumo_frame,
            text=f"Total de utilizadores {status_label}: {total_filtrados}    |    Eventos no periodo: {eventos_filtrados}",
            font=self.parent.fontes["subtitulo"],
            fg=self.parent.cores["texto_principal"],
            bg="#e8edf5",
        ).pack(anchor="w")

        contadores_frame = Frame(self.resumo_frame, bg="#e8edf5")
        contadores_frame.pack(anchor="w", pady=(2, 0))
        if total_ativos > 0:
            Label(
                contadores_frame,
                text=f"Ativos: {total_ativos}",
                font=self.parent.fontes["normal"],
                fg=self.parent.cores["texto_sucesso"],
                bg="#e8edf5",
            ).pack(side=LEFT, padx=(0, 15))
        if total_desativados > 0:
            Label(
                contadores_frame,
                text=f"Desativados: {total_desativados}",
                font=self.parent.fontes["normal"],
                fg=self.parent.cores["texto_aviso"],
                bg="#e8edf5",
            ).pack(side=LEFT, padx=(0, 15))
        if total_excluidos > 0:
            Label(
                contadores_frame,
                text=f"Excluidos: {total_excluidos}",
                font=self.parent.fontes["normal"],
                fg=self.parent.cores["texto_perigo"],
                bg="#e8edf5",
            ).pack(side=LEFT, padx=(0, 15))
        if status_filtro != "todos":
            Label(
                contadores_frame,
                text=f"(Filtro aplicado: {status_label.upper()})",
                font=self.parent.fontes["normal"],
                fg=self.parent.cores["texto_secundario"],
                bg="#e8edf5",
            ).pack(side=LEFT)

        responsaveis = Counter()
        for dados_u in utilizadores_filtrados.values():
            responsavel = dados_u.get("desativado_por") or dados_u.get("excluido_por")
            if responsavel:
                responsaveis[responsavel] += 1
        if responsaveis:
            nome_top, qtd_top = responsaveis.most_common(1)[0]
            plural = "ações" if qtd_top > 1 else "ação"
            Label(
                self.resumo_frame,
                text=f"Principal responsável por desativações/exclusões: {nome_top} ({qtd_top} {plural})",
                font=self.parent.fontes["normal"],
                fg=self.parent.cores["cor_roxo"],
                bg="#e8edf5",
            ).pack(anchor="w", pady=(2, 0))

        # --- Tabela (Treeview) ---
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.dados_tabela_atual = []
        linhas_texto = [
            f"{'#':<4} | {'Utilizador':<20} | {'Status':<14} | {'Eventos':>8} | {'Ultimo Evento':<20} | {'Modulos':<15}",
            "-" * 90,
        ]

        if utilizadores_ordenados:
            for i, (utilizador, dados) in enumerate(utilizadores_ordenados, 1):
                status_bruto = dados["status"]
                status_texto_col = f"[{status_bruto}]"
                tag = (
                    "ativo"
                    if status_bruto == "ATIVO"
                    else "desativado" if status_bruto == "DESATIVADO" else "excluido"
                )
                ultimo = dados["ultimo_evento"].strftime("%Y-%m-%d %H:%M")
                modulos_str = ", ".join(sorted(dados["modulos"]))

                self.tree.insert(
                    "",
                    END,
                    iid=utilizador,
                    values=(
                        i,
                        utilizador,
                        status_texto_col,
                        dados["total_eventos"],
                        ultimo,
                        modulos_str,
                    ),
                    tags=(tag,),
                )
                self.dados_tabela_atual.append(
                    [
                        str(i),
                        utilizador,
                        status_bruto,
                        str(dados["total_eventos"]),
                        ultimo,
                        modulos_str,
                    ]
                )
                linhas_texto.append(
                    f"{i:<4} | {utilizador[:20]:<20} | {status_texto_col:<14} | {dados['total_eventos']:>8} | {ultimo:<20} | {modulos_str}"
                )
        else:
            linhas_texto.append("Nenhum utilizador encontrado com o filtro selecionado.")

        # --- Texto equivalente, usado apenas para exportar em PDF ---
        texto = []
        texto.append("=" * 80)
        texto.append(f"  {titulo}")
        texto.append("=" * 80)
        texto.append("")
        texto.append("RESUMO:")
        texto.append(f"   Total de utilizadores {status_label}: {total_filtrados}")
        if total_ativos > 0:
            texto.append(f"   Ativos: {total_ativos}")
        if total_desativados > 0:
            texto.append(f"   Desativados: {total_desativados}")
        if total_excluidos > 0:
            texto.append(f"   Excluidos: {total_excluidos}")
        texto.append(f"\n   Eventos no periodo: {eventos_filtrados}")
        if status_filtro != "todos":
            texto.append(f"\n   Filtro aplicado: Mostrando apenas {status_label.upper()}")
        texto.append("")
        texto.extend(linhas_texto)
        texto.append("\n" + "=" * 80)
        texto.append("\nLEGENDA:")
        texto.append("   [ATIVO] - Utilizador que aparece nos logs (tem eventos registados)")
        texto.append("   [DESATIVADO] - Identificado por evento de desativacao no log")
        texto.append("   [EXCLUIDO] - Identificado por evento de exclusao no log")
        texto.append("\n" + "=" * 80)

        self.conteudo = "\n".join(texto)
        self.conteudo_atual = self.conteudo
        self.parent.ultimo_relatorio = self.conteudo

    def _get_status_label(self, status_filtro):
        labels = {
            "todos": "identificados",
            "ativos": "ativos",
            "desativados": "desativados",
            "excluidos": "excluidos",
        }
        return labels.get(status_filtro, "identificados")

    def _abrir_detalhe_utilizador(self, event):
        """Ao dar duplo clique numa linha, mostra os detalhes completos do utilizador"""
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        dados = self.utilizadores_extraidos.get(item_id)
        if not dados:
            return
        self._mostrar_popup_detalhe(item_id, dados)

    def _mostrar_popup_detalhe(self, utilizador, dados):
        detalhe = Toplevel(self.popup)
        detalhe.title(f"Detalhes - {utilizador}")
        detalhe.configure(bg="#e8edf5")
        detalhe.resizable(False, False)
        detalhe.transient(self.popup)
        detalhe.grab_set()

        largura, altura = 480, 420
        detalhe.update_idletasks()
        x = (detalhe.winfo_screenwidth() // 2) - (largura // 2)
        y = (detalhe.winfo_screenheight() // 2) - (altura // 2)
        detalhe.geometry(f"{largura}x{altura}+{x}+{y}")

        cor_status = {
            "ATIVO": self.parent.cores["texto_sucesso"],
            "DESATIVADO": self.parent.cores["texto_aviso"],
            "EXCLUIDO": self.parent.cores["texto_perigo"],
        }.get(dados["status"], self.parent.cores["texto_principal"])

        Label(
            detalhe,
            text=utilizador,
            font=self.parent.fontes["popup_titulo"],
            fg=self.parent.cores["texto_destaque"],
            bg="#e8edf5",
        ).pack(pady=(15, 2))
        Label(
            detalhe,
            text=f"[{dados['status']}]",
            font=self.parent.fontes["subtitulo"],
            fg=cor_status,
            bg="#e8edf5",
        ).pack(pady=(0, 12))

        corpo = Frame(detalhe, bg="#e8edf5")
        corpo.pack(fill=BOTH, expand=True, padx=20)

        def linha(rotulo, valor, cor=None):
            f = Frame(corpo, bg="#e8edf5")
            f.pack(fill=X, pady=3)
            Label(
                f,
                text=f"{rotulo}:",
                font=self.parent.fontes["botao"],
                fg=self.parent.cores["texto_principal"],
                bg="#e8edf5",
                width=20,
                anchor="w",
            ).pack(side=LEFT)
            Label(
                f,
                text=str(valor),
                font=self.parent.fontes["normal"],
                fg=cor or self.parent.cores["texto_secundario"],
                bg="#e8edf5",
                anchor="w",
                wraplength=260,
                justify=LEFT,
            ).pack(side=LEFT, fill=X, expand=True)

        linha("Total de eventos", dados["total_eventos"])
        linha("Primeiro evento", dados["primeiro_evento"].strftime("%Y-%m-%d %H:%M"))
        linha("Ultimo evento", dados["ultimo_evento"].strftime("%Y-%m-%d %H:%M"))
        linha("Modulos", ", ".join(sorted(dados["modulos"])) or "-")
        linha("Tipos de evento", ", ".join(sorted(dados["tipos_eventos"])) or "-")

        if dados["status"] == "DESATIVADO":
            Frame(corpo, bg=self.parent.cores["cor_borda"], height=1).pack(
                fill=X, pady=10
            )
            linha(
                "Desativado por",
                dados.get("desativado_por", "Desconhecido"),
                cor=self.parent.cores["texto_aviso"],
            )
            if dados.get("data_desativacao"):
                linha(
                    "Data da desativação",
                    dados["data_desativacao"].strftime("%Y-%m-%d %H:%M"),
                )
            if dados.get("descricao"):
                linha("Descrição do log", dados["descricao"])
        elif dados["status"] == "EXCLUIDO":
            Frame(corpo, bg=self.parent.cores["cor_borda"], height=1).pack(
                fill=X, pady=10
            )
            linha(
                "Excluído por",
                dados.get("excluido_por", "Desconhecido"),
                cor=self.parent.cores["texto_perigo"],
            )
            if dados.get("data_exclusao"):
                linha(
                    "Data da exclusão",
                    dados["data_exclusao"].strftime("%Y-%m-%d %H:%M"),
                )
            if dados.get("descricao"):
                linha("Descrição do log", dados["descricao"])

        Button(
            detalhe,
            text="Fechar",
            font=self.parent.fontes["botao"],
            bg=self.parent.cores["bg_botao"],
            fg="#ffffff",
            relief=FLAT,
            cursor="hand2",
            command=detalhe.destroy,
        ).pack(pady=15)

    def exportar_csv(self):
        """Exporta CSV APENAS com os dados dos utilizadores, com separador escolhido pelo usuario"""
        try:
            self.parent._log_terminal(
                "Iniciando exportacao CSV de utilizadores...", "INFO"
            )

            dados_tabela = self.dados_tabela_atual
            if not dados_tabela:
                self.parent._log_terminal(
                    "Nenhum dado de utilizadores encontrado para exportar!", "AVISO"
                )
                messagebox.showerror(
                    "Erro", "Nenhum dado de utilizadores encontrado para exportar!"
                )
                return None

            cabecalho = [
                "#",
                "Utilizador",
                "Status",
                "Eventos",
                "Ultimo Evento",
                "Modulos",
            ]

            separador = self.parent._popup_escolher_separador()
            if separador is None:
                self.parent._log_terminal(
                    "Exportacao CSV cancelada pelo usuario", "INFO"
                )
                return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"csv_utilizadores_{timestamp}.csv"
            caminho = PASTA_RELATORIOS / nome_arquivo

            with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=separador, quoting=csv.QUOTE_ALL)
                writer.writerow(cabecalho)
                for linha in dados_tabela:
                    writer.writerow(linha)

            self.parent._log_terminal(
                f"CSV de utilizadores gerado com sucesso: {caminho.name}", "SUCESSO"
            )

            try:
                os.startfile(str(caminho))
            except:
                pass

            messagebox.showinfo(
                "Sucesso",
                f"CSV exportado com sucesso!\n\nArquivo: {caminho.name}\nRegistros: {len(dados_tabela)}\nLocal: {caminho}",
            )
            return None

        except Exception as e:
            self.parent._log_terminal(
                f"ERRO ao exportar CSV de utilizadores: {e}", "ERRO"
            )
            messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")
            traceback.print_exc()
            return None


# ============================================================
# CLASSE: RelatorioDebug - IGUAL AO ORIGINAL
# ============================================================


class RelatorioDebug(RelatorioBase):
    def __init__(self, parent, text_widget):
        super().__init__(parent, text_widget, "DEBUG DO SISTEMA")
        self.tipo = "debug"

    def executar(self):
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
# CLASSE: RelatorioRelerLogs - IGUAL AO ORIGINAL
# ============================================================


class RelatorioRelerLogs:
    def __init__(self, parent):
        self.parent = parent

    def executar(self):
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
# CLASSE PRINCIPAL: InterfaceRelatorios - IGUAL AO ORIGINAL
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
            "bg_botao_utilitario": "#3a7a5a",
            "bg_botao_utilitario_hover": "#4a9a70",
            "bg_botao_debug": "#8a94a0",
            "bg_botao_debug_hover": "#9aa4b0",
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

    # ============================================================
    # MÉTODOS DE LOG E UTILITÁRIOS
    # ============================================================

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
        return None

    def _get_timestamp(self, evento):
        if hasattr(evento, "timestamp"):
            return evento.timestamp
        return datetime.now()

    def obter_export_config(self, tipo_relatorio):
        config = {
            "geral": {"pdf": True, "csv": True},
            "analitico": {"pdf": True, "csv": False},
            "detalhes": {"pdf": True, "csv": True},
            "utilizadores": {"pdf": True, "csv": True},
            "debug": {"pdf": True, "csv": False},
            "popup": {"pdf": True, "csv": True},
        }
        return config.get(tipo_relatorio, {"pdf": True, "csv": True})

    # ============================================================
    # MÉTODOS DE EXTRAÇÃO DE DADOS
    # ============================================================

    def _extrair_utilizadores_dos_eventos(self, eventos):
        """Extrai utilizadores dos eventos com identificacao de status"""
        # Usa a função do core.py
        return extrair_utilizadores_dos_eventos(eventos)

    def _extrair_dados_dos_logs(self, eventos):
        """Extrai estatísticas dos logs"""
        # Usa a função do core.py
        return extrair_estatisticas(eventos)

    # ============================================================
    # MÉTODOS DE EXPORTAÇÃO CSV
    # ============================================================

    def _popup_escolher_separador(self):
        """Pop-up pequeno para o usuario escolher o separador do CSV.

        Retorna "," ou ";" conforme a escolha, ou None se o usuario cancelar.
        """
        resultado = {"separador": None}

        largura, altura = 360, 240
        popup = Toplevel(self.root)
        popup.title("Separador do CSV")
        popup.configure(bg=self.cores["bg_principal"])
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (largura // 2)
        y = (popup.winfo_screenheight() // 2) - (altura // 2)
        popup.geometry(f"{largura}x{altura}+{x}+{y}")

        Label(
            popup,
            text="Separador do CSV",
            font=self.fontes["popup_titulo"],
            fg=self.cores["texto_principal"],
            bg=self.cores["bg_principal"],
        ).pack(pady=(18, 4))

        Label(
            popup,
            text="Como as colunas devem ser separadas\nno arquivo exportado?",
            font=self.fontes["normal"],
            fg=self.cores["texto_secundario"],
            bg=self.cores["bg_principal"],
            justify=LEFT,
        ).pack(pady=(0, 14))

        def escolher(separador):
            resultado["separador"] = separador
            popup.destroy()

        botoes_frame = Frame(popup, bg=self.cores["bg_principal"])
        botoes_frame.pack(pady=4)

        Button(
            botoes_frame,
            text="Vírgula ( , )\nBrasil / EUA",
            font=self.fontes["botao"],
            bg=self.cores["bg_botao"],
            fg="#ffffff",
            activebackground=self.cores["bg_botao_hover"],
            activeforeground="#ffffff",
            relief=FLAT,
            width=13,
            height=2,
            justify=LEFT,
            cursor="hand2",
            command=lambda: escolher(","),
        ).pack(side=LEFT, padx=8)

        Button(
            botoes_frame,
            text="Ponto e vírgula ( ; )\nEuropa e outros",
            font=self.fontes["botao"],
            bg=self.cores["bg_botao"],
            fg="#ffffff",
            activebackground=self.cores["bg_botao_hover"],
            activeforeground="#ffffff",
            relief=FLAT,
            width=16,
            height=2,
            justify=LEFT,
            cursor="hand2",
            command=lambda: escolher(";"),
        ).pack(side=LEFT, padx=8)

        Button(
            popup,
            text="Cancelar",
            font=self.fontes["normal"],
            bg=self.cores["bg_principal"],
            fg=self.cores["texto_secundario"],
            relief=FLAT,
            cursor="hand2",
            command=popup.destroy,
        ).pack(pady=(14, 0))

        popup.wait_window()
        return resultado["separador"]

    def _exportar_csv_popup(self, text_widget, titulo="relatorio"):
        """Exporta o conteúdo do popup para CSV"""
        try:
            self._log_terminal("Iniciando exportacao CSV do popup...", "INFO")
            conteudo = text_widget.get(1.0, END)
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum conteudo para exportar!")
                return None

            separador = self._popup_escolher_separador()
            if separador is None:
                self._log_terminal("Exportacao CSV cancelada pelo usuario", "INFO")
                return None

            # Usa o exportacao.py
            caminho = exportar_relatorio(conteudo, titulo, "csv", separador=separador)

            if caminho:
                self._log_terminal(f"CSV gerado com sucesso: {caminho.name}", "SUCESSO")
                try:
                    os.startfile(str(caminho))
                except:
                    pass
                messagebox.showinfo(
                    "Sucesso",
                    f"CSV exportado com sucesso!\n\nArquivo: {caminho.name}\nLocal: {caminho}",
                )
                return None

        except Exception as e:
            self._log_terminal(f"ERRO ao exportar CSV do popup: {e}", "ERRO")
            messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")
            traceback.print_exc()
            return None

    # ============================================================
    # MÉTODOS DE EXPORTAÇÃO PDF
    # ============================================================

    def _exportar_pdf_com_molde(self, conteudo, titulo, tipo="popup"):
        """Exporta PDF usando o exportacao.py"""
        try:
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror(
                    "Erro",
                    "Nenhum relatorio para exportar! Execute uma consulta primeiro.",
                )
                return

            self._log_terminal(f"Iniciando exportacao PDF para: {titulo}", "INFO")

            # Usa o exportacao.py
            caminho = exportar_relatorio(conteudo, titulo, "pdf", estilo="padrao")

            if caminho:
                self._log_terminal(f"PDF gerado com sucesso: {caminho.name}", "SUCESSO")
                try:
                    os.startfile(str(caminho))
                except:
                    pass
                messagebox.showinfo(
                    "Sucesso",
                    f"PDF exportado com sucesso!\n\nArquivo: {caminho.name}\nLocal: {caminho}",
                )

        except Exception as e:
            self._log_terminal(f"ERRO ao exportar PDF: {e}", "ERRO")
            traceback.print_exc()
            messagebox.showerror(
                "Erro", f"Erro ao exportar PDF: {e}\n\n{traceback.format_exc()}"
            )

    def _exportar_pdf_consulta(self, conteudo, titulo):
        """Exporta PDF específico para consulta"""
        try:
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum relatorio para exportar!")
                return

            self._log_terminal(
                f"Iniciando exportacao PDF da consulta: {titulo}", "INFO"
            )

            # Usa o exportacao.py com estilo consulta
            caminho = exportar_relatorio(conteudo, titulo, "pdf", estilo="consulta")

            if caminho:
                self._log_terminal(f"PDF da consulta gerado: {caminho.name}", "SUCESSO")
                try:
                    os.startfile(str(caminho))
                except:
                    pass
                messagebox.showinfo(
                    "Sucesso",
                    f"PDF exportado com sucesso!\n\nArquivo: {caminho.name}\nLocal: {caminho}",
                )

        except Exception as e:
            self._log_terminal(f"ERRO ao exportar PDF da consulta: {e}", "ERRO")
            traceback.print_exc()
            messagebox.showerror(
                "Erro", f"Erro ao exportar PDF: {e}\n\n{traceback.format_exc()}"
            )

    def _exportar_pdf_detalhamento(self, conteudo, titulo):
        """Exporta PDF específico para detalhamento"""
        try:
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum relatorio para exportar!")
                return

            self._log_terminal(
                f"Iniciando exportacao PDF do detalhamento: {titulo}", "INFO"
            )

            # Usa o exportacao.py com estilo detalhamento
            caminho = exportar_relatorio(conteudo, titulo, "pdf", estilo="detalhamento")

            if caminho:
                self._log_terminal(
                    f"PDF do detalhamento gerado: {caminho.name}", "SUCESSO"
                )
                try:
                    os.startfile(str(caminho))
                except:
                    pass
                messagebox.showinfo(
                    "Sucesso",
                    f"PDF exportado com sucesso!\n\nArquivo: {caminho.name}\nLocal: {caminho}",
                )

        except Exception as e:
            self._log_terminal(f"ERRO ao exportar PDF do detalhamento: {e}", "ERRO")
            traceback.print_exc()
            messagebox.showerror(
                "Erro", f"Erro ao exportar PDF: {e}\n\n{traceback.format_exc()}"
            )

    def _exportar_pdf_analitico(self, conteudo, titulo):
        """Exporta PDF específico para o Relatório Analítico"""
        try:
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum relatorio para exportar!")
                return

            self._log_terminal(
                f"Iniciando exportacao PDF do Relatorio Analitico: {titulo}", "INFO"
            )

            # Usa o exportacao.py com estilo analitico
            caminho = exportar_relatorio(conteudo, titulo, "pdf", estilo="analitico")

            if caminho:
                self._log_terminal(f"PDF Analitico gerado: {caminho.name}", "SUCESSO")
                try:
                    os.startfile(str(caminho))
                except:
                    pass
                messagebox.showinfo(
                    "Sucesso",
                    f"PDF exportado com sucesso!\n\nArquivo: {caminho.name}\nLocal: {caminho}",
                )

        except Exception as e:
            self._log_terminal(f"ERRO ao exportar PDF Analitico: {e}", "ERRO")
            traceback.print_exc()
            messagebox.showerror(
                "Erro", f"Erro ao exportar PDF: {e}\n\n{traceback.format_exc()}"
            )

    # ============================================================
    # MÉTODOS DE INTERFACE
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
        self._criar_cards_resumo()
        self._criar_saida()

    def _criar_cards_resumo(self):
        cards_frame = Frame(self.conteudo_frame, bg=self.cores["bg_principal"])
        cards_frame.pack(fill=X, pady=(0, 15))

        self.cards_valores = {}
        definicoes = [
            ("total", "📊", "Total de Eventos", self.cores["cor_azul"]),
            ("critical", "🔴", "Críticos", self.cores["texto_perigo"]),
            ("warning", "🟠", "Avisos", self.cores["texto_aviso"]),
            ("utilizadores", "👥", "Utilizadores", self.cores["cor_roxo"]),
            ("atualizado", "🕐", "Última Leitura", self.cores["texto_secundario"]),
        ]

        for i, (chave, icone, rotulo, cor) in enumerate(definicoes):
            card = Frame(
                cards_frame,
                bg=self.cores["bg_card"],
                highlightbackground=self.cores["cor_borda"],
                highlightthickness=1,
            )
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            Label(
                card,
                text=icone,
                font=self.fontes["card_icone"],
                bg=self.cores["bg_card"],
            ).pack(pady=(10, 0))
            valor_label = Label(
                card,
                text="-",
                font=self.fontes["card_valor"],
                fg=cor,
                bg=self.cores["bg_card"],
            )
            valor_label.pack()
            Label(
                card,
                text=rotulo,
                font=self.fontes["status"],
                fg=self.cores["texto_secundario"],
                bg=self.cores["bg_card"],
            ).pack(pady=(0, 10))
            self.cards_valores[chave] = valor_label

        for i in range(len(definicoes)):
            cards_frame.grid_columnconfigure(i, weight=1)

    def _atualizar_cards_resumo(self):
        if not hasattr(self, "cards_valores"):
            return
        total = self.dados.get("total_eventos", 0)
        critical = self.dados.get("critical", 0)
        warning = self.dados.get("warning", 0)
        utilizadores = self.dados.get("utilizadores")
        n_utilizadores = len(utilizadores) if utilizadores else 0

        self.cards_valores["total"].config(text=str(total))
        self.cards_valores["critical"].config(text=str(critical))
        self.cards_valores["warning"].config(text=str(warning))
        self.cards_valores["utilizadores"].config(text=str(n_utilizadores))
        self.cards_valores["atualizado"].config(text=datetime.now().strftime("%H:%M"))

    def _criar_botoes(self):
        botoes_frame = Frame(self.conteudo_frame, bg=self.cores["bg_principal"])
        botoes_frame.pack(fill=X, pady=(0, 15))

        # --- Grupo 1: Relatórios (visualização de dados) ---
        Label(
            botoes_frame,
            text="RELATÓRIOS",
            font=self.fontes["status"],
            fg=self.cores["texto_secundario"],
            bg=self.cores["bg_principal"],
        ).pack(anchor="w", pady=(0, 4))

        relatorios_frame = Frame(botoes_frame, bg=self.cores["bg_principal"])
        relatorios_frame.pack(fill=X)

        botoes_relatorios = [
            ("🔍  Consulta Geral Sistema", self._abrir_consulta),
            ("📋  Detalhar Eventos por módulo", self._abrir_detalhes),
            ("📊  Relatório Analítico", self._abrir_analitico),
            ("👥  Relatório Utilizadores", self._abrir_utilizadores),
        ]
        self._criar_grupo_botoes(
            relatorios_frame,
            botoes_relatorios,
            bg=self.cores["bg_botao"],
            bg_hover=self.cores["bg_botao_hover"],
            colunas=4,
        )

        # --- Separador entre os grupos ---
        Frame(botoes_frame, bg=self.cores["cor_borda"], height=1).pack(
            fill=X, pady=(14, 10)
        )

        # --- Grupo 2: Ferramentas e ações (natureza diferente de um relatório) ---
        Label(
            botoes_frame,
            text="FERRAMENTAS E AÇÕES",
            font=self.fontes["status"],
            fg=self.cores["texto_secundario"],
            bg=self.cores["bg_principal"],
        ).pack(anchor="w", pady=(0, 4))

        ferramentas_frame = Frame(botoes_frame, bg=self.cores["bg_principal"])
        ferramentas_frame.pack(fill=X)

        botoes_ferramentas = [
            (
                "🔄  Reler Logs",
                self._abrir_reler_logs,
                self.cores["bg_botao_utilitario"],
                self.cores["bg_botao_utilitario_hover"],
            ),
            (
                "🛠️  Debug",
                self._abrir_debug,
                self.cores["bg_botao_debug"],
                self.cores["bg_botao_debug_hover"],
            ),
        ]
        for i, (texto, comando, cor_bg, cor_hover) in enumerate(botoes_ferramentas):
            btn = Button(
                ferramentas_frame,
                text=texto,
                font=self.fontes["botao"],
                bg=cor_bg,
                fg="#ffffff",
                relief=FLAT,
                cursor="hand2",
                padx=15,
                pady=8,
                command=comando,
            )
            btn.grid(row=0, column=i, padx=6, pady=2, sticky="ew")

            def on_enter(e, b=btn, cor=cor_hover):
                b.config(bg=cor)

            def on_leave(e, b=btn, cor=cor_bg):
                b.config(bg=cor)

            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

        for i in range(2):
            ferramentas_frame.grid_columnconfigure(i, weight=0, minsize=180)

    def _criar_grupo_botoes(self, frame_pai, botoes, bg, bg_hover, colunas):
        """Cria um grid de botoes com a mesma cor, usado para agrupar por categoria"""
        for i, (texto, comando) in enumerate(botoes):
            btn = Button(
                frame_pai,
                text=texto,
                font=self.fontes["botao"],
                bg=bg,
                fg="#ffffff",
                relief=FLAT,
                cursor="hand2",
                padx=15,
                pady=10,
                command=comando,
            )
            btn.grid(
                row=i // colunas, column=i % colunas, padx=6, pady=6, sticky="ew"
            )

            def on_enter(e, b=btn, cor=bg_hover):
                b.config(bg=cor)

            def on_leave(e, b=btn, cor=bg):
                b.config(bg=cor)

            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
        for i in range(colunas):
            frame_pai.grid_columnconfigure(i, weight=1)

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

            # ============================================================
            # USA O core.py PARA INICIALIZAR E LER LOGS
            # ============================================================
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
                self._atualizar_cards_resumo()
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
            self._atualizar_cards_resumo()
        except Exception as e:
            self._escrever_saida(f"Erro ao atualizar resumo: {e}\n", "error")
            traceback.print_exc()

    # ============================================================
    # MÉTODOS PARA ABRIR RELATORIOS
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
        relatorio = RelatorioDetalhes(self)
        relatorio.executar()

    def _abrir_analitico(self):
        popup = self._criar_popup("Relatorio Analitico", 950, 750)
        Label(
            popup,
            text="RELATORIO ANALITICO",
            font=self.fontes["popup_titulo"],
            fg=self.cores["texto_destaque"],
            bg="#e8edf5",
        ).pack(pady=(15, 5))

        # Area do grafico: criada aqui, direto na thread principal (a mesma
        # thread do clique no botao), por isso e seguro. Nao depende da
        # geracao do texto do RelatorioAnalitico, que roda numa thread separada.
        grafico_frame = Frame(popup, bg="#e8edf5", height=250)
        grafico_frame.pack(fill=X, padx=15, pady=(0, 10))
        grafico_frame.pack_propagate(False)
        self._criar_grafico_analitico(grafico_frame)

        text = scrolledtext.ScrolledText(
            popup,
            font=self.fontes["saida"],
            bg="#ffffff",
            fg="#000000",
            wrap=WORD,
            height=20,
        )
        text.pack(fill=BOTH, expand=True, padx=15, pady=(0, 10))
        self._configurar_tags_texto(text)
        relatorio = RelatorioAnalitico(self, text)
        self._executar_relatorio(relatorio, popup)

    def _criar_grafico_analitico(self, container):
        """Gera um resumo visual (pizza de severidade + barras por modulo)
        usando dados que ja estao prontos em self.dados. Nao depende de
        nenhuma thread - e chamado direto de _abrir_analitico."""
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            Label(
                container,
                text=(
                    "Para ver os graficos, instale a biblioteca matplotlib:\n"
                    "pip install matplotlib"
                ),
                font=self.fontes["normal"],
                fg=self.cores["texto_aviso"],
                bg="#e8edf5",
                justify=LEFT,
            ).pack(pady=20)
            return

        critical = self.dados.get("critical", 0)
        warning = self.dados.get("warning", 0)
        info = self.dados.get("info", 0)
        modulos = self.dados.get("modulos", {})

        if not (critical or warning or info):
            Label(
                container,
                text="Sem dados suficientes para gerar graficos.",
                font=self.fontes["normal"],
                fg=self.cores["texto_secundario"],
                bg="#e8edf5",
            ).pack(pady=20)
            return

        try:
            fig = Figure(figsize=(8.5, 2.6), dpi=100)
            fig.patch.set_facecolor("#e8edf5")

            # --- Grafico 1: distribuicao por severidade ---
            ax1 = fig.add_subplot(1, 2, 1)
            valores, labels, cores_pizza = [], [], []
            if critical > 0:
                valores.append(critical)
                labels.append("CRITICAL")
                cores_pizza.append("#cc3333")
            if warning > 0:
                valores.append(warning)
                labels.append("WARNING")
                cores_pizza.append("#cc8800")
            if info > 0:
                valores.append(info)
                labels.append("INFO")
                cores_pizza.append("#1a6c9a")
            ax1.pie(
                valores,
                labels=labels,
                autopct="%1.0f%%",
                colors=cores_pizza,
                textprops={"fontsize": 8},
            )
            ax1.set_title("Eventos por Severidade", fontsize=9, color="#1a2a4a")

            # --- Grafico 2: eventos por modulo ---
            ax2 = fig.add_subplot(1, 2, 2)
            if modulos:
                modulos_ordenados = sorted(
                    modulos.items(), key=lambda x: x[1], reverse=True
                )[:6]
                nomes = [m for m, _ in modulos_ordenados]
                contagens = [c for _, c in modulos_ordenados]
                ax2.bar(nomes, contagens, color="#1a5c8a")
                ax2.set_title("Eventos por Modulo", fontsize=9, color="#1a2a4a")
                ax2.tick_params(axis="x", labelrotation=30, labelsize=7)
                ax2.tick_params(axis="y", labelsize=7)
            else:
                ax2.axis("off")
                ax2.text(
                    0.5, 0.5, "Sem dados de modulo", ha="center", va="center", fontsize=8
                )

            fig.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=BOTH, expand=True)
        except Exception as e:
            Label(
                container,
                text=f"Nao foi possivel gerar o grafico: {e}",
                font=self.fontes["normal"],
                fg=self.cores["texto_perigo"],
                bg="#e8edf5",
                wraplength=700,
            ).pack(pady=20)
            traceback.print_exc()

    def _abrir_utilizadores(self):
        relatorio = RelatorioUtilizadores(self)
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
        text_widget.tag_configure(
            "alerta",
            foreground="#ffffff",
            background="#cc3333",
            font=("Consolas", 10, "bold"),
        )

    def _executar_relatorio(self, relatorio, popup):
        def executar_thread():
            try:
                relatorio.executar()
            except Exception as e:
                self._log_terminal(f"ERRO na execução do relatório: {e}", "ERRO")
                traceback.print_exc()

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