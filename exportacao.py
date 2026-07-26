"""
exportacao.py - Gerencia exportação para PDF e CSV
"""
import csv
import re
import os
import sys
import traceback
from pathlib import Path
from datetime import datetime
from tkinter import messagebox, simpledialog

# Importa do core
from core import PASTA_RELATORIOS, Evento, EstadoDoSistema

# ============================================================
# VERIFICA DISPONIBILIDADE DO REPORTLAB
# ============================================================

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.graphics.shapes import Drawing, Line, Rect
    REPORTLAB_DISPONIVEL = True
except ImportError:
    REPORTLAB_DISPONIVEL = False
    print("[AVISO] ReportLab não instalado. Execute: pip install reportlab")


# ============================================================
# FUNÇÃO PARA PERGUNTAR SEPARADOR
# ============================================================

def perguntar_separador():
    """Pergunta ao usuário qual separador usar"""
    separador_opcao = simpledialog.askstring(
        "Separador CSV",
        "Escolha o separador para o CSV:\n\n"
        "1 - Ponto e virgula (;) - Excel PT-BR/PT-PT\n"
        "2 - Virgula (,) - Excel EN-US/Internacional\n\n"
        "Digite 1 ou 2:",
        parent=None
    )
    
    if separador_opcao == "1":
        return ";"
    elif separador_opcao == "2":
        return ","
    else:
        return ";"


# ============================================================
# FUNÇÃO: exportar_csv_dados() - SOLUÇÃO 2
# ============================================================

def exportar_csv_dados(eventos, titulo, tipo="eventos", separador=None):
    """
    Exporta CSV diretamente dos eventos (dados brutos)
    """
    try:
        if not eventos:
            raise ValueError("Nenhum evento para exportar")
        
        if separador is None:
            separador = perguntar_separador()
        
        # Gera o nome do arquivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sep_nome = "ponto_virgula" if separador == ";" else "virgula"
        titulo_limpo = titulo.replace(" ", "_").replace("-", "_").lower()
        titulo_limpo = re.sub(r"[^a-zA-Z0-9_]", "", titulo_limpo)
        nome_arquivo = f"{titulo_limpo}_{sep_nome}_{timestamp}.csv"
        caminho = PASTA_RELATORIOS / nome_arquivo
        
        # PREPARA OS DADOS
        if tipo == "utilizadores":
            cabecalho = ["#", "Utilizador", "Status", "Eventos", "Ultimo_Evento", "Modulos"]
            dados = _extrair_dados_utilizadores(eventos)
        else:
            cabecalho = ["ID", "Data/Hora", "Status", "Modulo", "Observacao", "Utilizador"]
            dados = _extrair_dados_eventos(eventos)
        
        if not dados:
            raise ValueError("Nenhum dado para exportar")
        
        # ESCREVE O CSV
        with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=separador, quoting=csv.QUOTE_ALL)
            writer.writerow(cabecalho)
            for linha in dados:
                writer.writerow(linha)
        
        # ABRE O ARQUIVO
        try:
            if sys.platform == "win32":
                os.startfile(str(caminho))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", str(caminho)])
            else:
                import subprocess
                subprocess.run(["xdg-open", str(caminho)])
        except:
            pass
        
        nome_separador = "ponto e virgula (;)" if separador == ";" else "virgula (,)"
        messagebox.showinfo(
            "Sucesso",
            f"CSV exportado com sucesso!\n\n"
            f"Arquivo: {caminho.name}\n"
            f"Separador: {nome_separador}\n"
            f"Registros: {len(dados)}\n"
            f"Local: {caminho}"
        )
        
        return str(caminho)
        
    except Exception as e:
        print(f"ERRO ao exportar CSV: {e}")
        traceback.print_exc()
        messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")
        return None


# ============================================================
# FUNÇÕES AUXILIARES PARA EXTRAIR DADOS
# ============================================================

def _extrair_dados_eventos(eventos):
    """Extrai dados de eventos para CSV"""
    dados = []
    
    for idx, evento in enumerate(eventos, 1):
        if hasattr(evento, 'payload') and isinstance(evento.payload, dict):
            payload = evento.payload
            data_hora = evento.timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(evento, 'timestamp') else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            modulo = payload.get("modulo", "DESCONHECIDO")
            severidade = payload.get("severidade", "INFO")
            descricao = payload.get("descricao", "")
            utilizador = payload.get("utilizador", "Desconhecido")
            
            status = "CRITICO" if severidade == "CRITICAL" else "ATENCAO" if severidade == "WARNING" else "INFO"
            
            dados.append([
                str(idx),
                data_hora,
                status,
                modulo,
                descricao[:200] if descricao else "",
                utilizador
            ])
    
    return dados


def _extrair_dados_utilizadores(eventos):
    """Extrai dados de utilizadores para CSV"""
    from core import extrair_utilizadores_dos_eventos
    
    utilizadores = extrair_utilizadores_dos_eventos(eventos)
    dados = []
    
    for idx, (utilizador, dados_user) in enumerate(utilizadores.items(), 1):
        ultimo = dados_user["ultimo_evento"].strftime("%Y-%m-%d %H:%M")
        modulos_str = ", ".join(list(dados_user["modulos"])[:3])
        if len(dados_user["modulos"]) > 3:
            modulos_str += f" +{len(dados_user['modulos'])-3}"
        
        dados.append([
            str(idx),
            utilizador,
            dados_user["status"],
            str(dados_user["total_eventos"]),
            ultimo,
            modulos_str
        ])
    
    return dados


# ============================================================
# FUNÇÃO: exportar_relatorio() - SOLUÇÃO 2
# ============================================================

def exportar_relatorio(conteudo, titulo, tipo="pdf", **kwargs):
    """
    Função principal para exportar relatórios.
    
    Args:
        conteudo: Texto formatado ou None (se usar dados_brutos)
        titulo: Título do relatório
        tipo: "pdf" ou "csv"
        **kwargs: 
            - dados_brutos: lista de eventos (para exportar dados crus)
            - tipo_dados: "eventos" ou "utilizadores"
            - separador: ";" ou ","
    """
    
    # Verifica se recebeu dados brutos
    dados_brutos = kwargs.get("dados_brutos", None)
    tipo_dados = kwargs.get("tipo_dados", "eventos")
    separador = kwargs.get("separador", None)
    
    # SE FOR PDF
    if tipo.lower() == "pdf":
        exportador = ExportadorPDF()
        return exportador.exportar(conteudo, titulo, **kwargs)
    
    # SE FOR CSV
    elif tipo.lower() == "csv":
        # Se recebeu dados brutos, usa a função especial
        if dados_brutos is not None:
            return exportar_csv_dados(dados_brutos, titulo, tipo=tipo_dados, separador=separador)
        else:
            # Fallback: usa o exportador CSV existente
            exportador = ExportadorCSV()
            return exportador.exportar(conteudo, titulo, **kwargs)
    
    else:
        raise ValueError(f"Tipo de exportação inválido: {tipo}")


# ============================================================
# CLASSE BASE: ExportadorBase
# ============================================================

class ExportadorBase:
    """Classe base para exportadores"""
    
    def __init__(self, pasta_destino=None):
        self.pasta_destino = pasta_destino or PASTA_RELATORIOS
        self.pasta_destino.mkdir(parents=True, exist_ok=True)
        self.ultimo_arquivo = None
    
    def _gerar_nome_arquivo(self, titulo, extensao, separador=None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_limpo = titulo.replace(" ", "_").replace("-", "_").lower()
        nome_limpo = re.sub(r"[^a-zA-Z0-9_]", "", nome_limpo)
        
        if separador:
            if separador == ";":
                sep_nome = "ponto_virgula"
            elif separador == ",":
                sep_nome = "virgula"
            else:
                sep_nome = "separador"
            return f"{nome_limpo}_{sep_nome}_{timestamp}.{extensao}"
        
        return f"{nome_limpo}_{timestamp}.{extensao}"
    
    def _abrir_arquivo(self, caminho):
        try:
            if sys.platform == "win32":
                os.startfile(str(caminho))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", str(caminho)])
            else:
                import subprocess
                subprocess.run(["xdg-open", str(caminho)])
        except Exception:
            pass
    
    def exportar(self, conteudo, titulo, **kwargs):
        raise NotImplementedError("Subclasses devem implementar exportar()")


# ============================================================
# EXPORTADOR CSV (Fallback)
# ============================================================

class ExportadorCSV(ExportadorBase):
    """Exporta relatórios para CSV (texto formatado)"""
    
    def exportar(self, conteudo, titulo, **kwargs):
        try:
            if not conteudo or conteudo.strip() == "":
                raise ValueError("Nenhum conteúdo para exportar")
            
            tipo = kwargs.get("tipo", "generico")
            separador = kwargs.get("separador", None)
            
            if separador is None:
                separador = perguntar_separador()
            
            nome_arquivo = self._gerar_nome_arquivo(titulo, "csv", separador)
            caminho = self.pasta_destino / nome_arquivo
            
            # Extrai os dados da tabela
            dados_tabela = self._extrair_dados_tabela(conteudo)
            
            cabecalho = ["ID", "Data/Hora", "Status", "Modulo", "Observacao", "Utilizador"]
            if tipo == "utilizadores":
                cabecalho = ["#", "Utilizador", "Status", "Eventos", "Ultimo_Evento", "Modulos"]
            
            if not dados_tabela:
                self._exportar_como_texto(conteudo, caminho, separador)
            else:
                with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f, delimiter=separador, quoting=csv.QUOTE_ALL)
                    writer.writerow(cabecalho)
                    for linha in dados_tabela:
                        writer.writerow(linha)
            
            self.ultimo_arquivo = caminho
            self._abrir_arquivo(caminho)
            
            return caminho
            
        except Exception as e:
            print(f"ERRO ao exportar CSV: {e}")
            traceback.print_exc()
            raise
    
    def _extrair_dados_tabela(self, conteudo):
        linhas = conteudo.split("\n")
        dados = []
        modo_tabela = False
        cabecalho_ignorado = False
        
        for linha in linhas:
            linha = linha.strip()
            
            if not linha:
                continue
            
            if "|" in linha and "ID" in linha and "Data/Hora" in linha:
                modo_tabela = True
                cabecalho_ignorado = True
                continue
            
            if "|" in linha and "#" in linha and "Utilizador" in linha:
                modo_tabela = True
                cabecalho_ignorado = True
                continue
            
            if cabecalho_ignorado and "|" in linha and modo_tabela:
                linha_clean = linha
                if linha_clean.startswith("|"):
                    linha_clean = linha_clean[1:]
                if linha_clean.endswith("|"):
                    linha_clean = linha_clean[:-1]
                
                linha_clean = (linha_clean
                    .replace("[ATIVO]", "ATIVO")
                    .replace("[DESATIVADO]", "DESATIVADO")
                    .replace("[EXCLUIDO]", "EXCLUIDO")
                )
                
                partes = [p.strip() for p in linha_clean.split("|") if p.strip()]
                
                if len(partes) >= 5:
                    while len(partes) < 6:
                        partes.append("")
                    dados.append(partes[:6])
        
        return dados
    
    def _exportar_como_texto(self, conteudo, caminho, separador=";"):
        linhas = conteudo.split("\n")
        
        with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=separador, quoting=csv.QUOTE_ALL)
            writer.writerow(["Linha", "Conteudo"])
            
            for i, linha in enumerate(linhas, 1):
                linha = linha.strip()
                if linha:
                    writer.writerow([str(i), linha])


# ============================================================
# EXPORTADOR PDF
# ============================================================

class ExportadorPDF(ExportadorBase):
    """Exporta relatórios para PDF"""
    
    def exportar(self, conteudo, titulo, **kwargs):
        if not REPORTLAB_DISPONIVEL:
            raise ImportError("ReportLab não está instalado. Execute: pip install reportlab")
        
        try:
            if not conteudo or conteudo.strip() == "":
                raise ValueError("Nenhum conteúdo para exportar")
            
            estilo = kwargs.get("estilo", "padrao")
            nome_arquivo = self._gerar_nome_arquivo(titulo, "pdf")
            caminho = self.pasta_destino / nome_arquivo
            
            self._exportar_padrao(conteudo, titulo, caminho)
            
            self.ultimo_arquivo = caminho
            self._abrir_arquivo(caminho)
            return caminho
            
        except Exception as e:
            print(f"ERRO ao exportar PDF: {e}")
            traceback.print_exc()
            raise
    
    def _criar_estilos_pdf(self):
        styles = getSampleStyleSheet()
        
        cor_primaria = HexColor("#1a5276")
        cor_secundaria = HexColor("#2980b9")
        cor_texto = HexColor("#1a2a4a")
        
        estilo_titulo = ParagraphStyle(
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
        
        estilo_normal = ParagraphStyle(
            "NormalPersonalizado",
            parent=styles["Normal"],
            fontSize=8,
            alignment=TA_LEFT,
            textColor=cor_texto,
            fontName="Helvetica",
            leading=11,
        )
        
        estilo_rodape = ParagraphStyle(
            "Rodape",
            parent=styles["Normal"],
            fontSize=7,
            alignment=TA_CENTER,
            textColor=HexColor("#5d6d7e"),
            fontName="Helvetica-Oblique",
            leading=10,
        )
        
        return {
            "titulo": estilo_titulo,
            "subtitulo": estilo_subtitulo,
            "normal": estilo_normal,
            "rodape": estilo_rodape,
        }
    
    def _exportar_padrao(self, conteudo, titulo, caminho):
        doc = SimpleDocTemplate(
            str(caminho),
            pagesize=A4,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
        )
        
        story = []
        estilos = self._criar_estilos_pdf()
        
        story.append(Paragraph("SISTEMA INTEGRADO DE SEGURANCA", estilos["titulo"]))
        story.append(Paragraph(titulo, estilos["subtitulo"]))
        
        linha = Drawing(720, 4)
        linha.add(Line(150, 2, 570, 2, strokeColor=HexColor("#1a5276"), strokeWidth=2))
        story.append(linha)
        story.append(Spacer(1, 10))
        
        for linha_texto in conteudo.split("\n"):
            linha_texto = linha_texto.rstrip()
            if not linha_texto.strip():
                story.append(Spacer(1, 3))
                continue
            story.append(Paragraph(linha_texto, estilos["normal"]))
            story.append(Spacer(1, 2))
        
        story.append(Spacer(1, 15))
        linha_inferior = Drawing(720, 4)
        linha_inferior.add(Line(0, 2, 720, 2, strokeColor=HexColor("#1a5276"), strokeWidth=1.5))
        story.append(linha_inferior)
        story.append(Spacer(1, 6))
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        story.append(Paragraph(
            "Relatório gerado automaticamente pelo Sistema Integrado de Segurança",
            estilos["rodape"]
        ))
        story.append(Paragraph(
            f"Documento: REL-{datetime.now().strftime('%Y%m%d')}-{timestamp[-4:]} | Versão: 1.0",
            estilos["rodape"]
        ))
        
        doc.build(story)