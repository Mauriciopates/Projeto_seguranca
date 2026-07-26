"""
ui.py - Interface gráfica principal
puxando informações do core.py e exportacao.py
"""

import os
import csv
import io
import threading
import traceback
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
    StringVar,  # Variável para texto em Radiobutton
    END,  # Constante para final do texto
    WORD,  # Constante para quebra de palavra
    DISABLED,  # Estado desabilitado de widget
    NORMAL,  # Estado normal de widget
    FLAT,  # Estilo de relevo plano
    LEFT,  # Alinhamento à esquerda
    RIGHT,  # Alinhamento à direita
    X,  # Preenchimento horizontal
    BOTH,  # Preenchimento em ambos os eixos
)

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
    def __init__(self, parent, text_widget):
        super().__init__(parent, text_widget, "DETALHAMENTO DE EVENTOS POR MODULO")
        self.tipo = "detalhes"
        self.modulos_encontrados = {}

    def executar(self):
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
        """Exporta o PDF do detalhamento com formatação IDÊNTICA à tela"""
        try:
            conteudo = self.obter_conteudo()
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum conteudo para exportar!")
                return
            self.parent._exportar_pdf_detalhamento(conteudo, self.titulo)
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
        if text_widget is None:
            text_widget = scrolledtext.ScrolledText(
                parent.root if parent else None,
                font=parent.fontes["saida"] if parent else ("Consolas", 10),
                bg="#ffffff",
                fg="#000000",
                wrap=WORD,
                height=25,
            )
        super().__init__(parent, text_widget, "RELATORIO DE UTILIZADORES")
        self.tipo = "utilizadores"
        self.utilizadores_extraidos = {}
        self.filtro_status = StringVar(value="todos")
        self.conteudo_atual = ""
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
            END, f"   Total de utilizadores {status_label}: {total_filtrados}\n", "info"
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
                END, f"\n   Filtro aplicado: Mostrando apenas {status_nome}\n", "info"
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
            END, "   [EXCLUIDO] - Identificado por evento de exclusao no log\n", "error"
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

    def exportar_csv(self):
        """Exporta CSV APENAS com os dados dos utilizadores, com separador escolhido pelo usuario"""
        try:
            self.parent._log_terminal(
                "Iniciando exportacao CSV de utilizadores...", "INFO"
            )

            conteudo = self.text_widget.get(1.0, END)
            if not conteudo or conteudo.strip() == "":
                messagebox.showerror("Erro", "Nenhum conteudo para exportar!")
                return None

            linhas = conteudo.split("\n")
            dados_tabela = []
            cabecalho = [
                "#",
                "Utilizador",
                "Status",
                "Eventos",
                "Ultimo Evento",
                "Modulos",
            ]
            cabecalho_encontrado = False

            for linha in linhas:
                linha = linha.strip()

                if "|" in linha and "Utilizador" in linha and "Status" in linha:
                    cabecalho_encontrado = True
                    continue

                if cabecalho_encontrado and "|" in linha:
                    linha_clean = (
                        linha.replace("[ATIVO]", "ATIVO")
                        .replace("[DESATIVADO]", "DESATIVADO")
                        .replace("[EXCLUIDO]", "EXCLUIDO")
                        .strip()
                    )

                    partes = [p.strip() for p in linha_clean.split("|") if p.strip()]

                    if len(partes) >= 5:
                        while len(partes) < 6:
                            partes.append("")
                        dados_tabela.append(partes)

            if not dados_tabela:
                self.parent._log_terminal(
                    "Nenhum dado de utilizadores encontrado para exportar!", "AVISO"
                )
                messagebox.showerror(
                    "Erro", "Nenhum dado de utilizadores encontrado para exportar!"
                )
                return None

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