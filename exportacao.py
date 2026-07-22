"""
exportacao.py - Gerencia exportação para PDF e CSV
Herda e utiliza as classes do config.py
"""
import csv
import re
import os
import sys
import traceback
from pathlib import Path
from datetime import datetime
from tkinter import messagebox

# Importa do config
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
# CLASSE BASE: ExportadorBase
# ============================================================

class ExportadorBase:
    """Classe base para exportadores"""
    
    def __init__(self, pasta_destino=None):
        self.pasta_destino = pasta_destino or PASTA_RELATORIOS
        self.pasta_destino.mkdir(parents=True, exist_ok=True)
        self.ultimo_arquivo = None
    
    def _gerar_nome_arquivo(self, titulo, extensao):
        """Gera nome único para o arquivo"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_limpo = titulo.replace(" ", "_").replace("-", "_").lower()
        nome_limpo = re.sub(r"[^a-zA-Z0-9_]", "", nome_limpo)
        return f"{nome_limpo}_{timestamp}.{extensao}"
    
    def _abrir_arquivo(self, caminho):
        """Abre o arquivo com o programa padrão"""
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
        """Método a ser sobrescrito pelas subclasses"""
        raise NotImplementedError("Subclasses devem implementar exportar()")


# ============================================================
# EXPORTADOR CSV (Herda de ExportadorBase)
# ============================================================

class ExportadorCSV(ExportadorBase):
    """Exporta relatórios para CSV"""
    
    def exportar(self, conteudo, titulo, **kwargs):
        """Exporta conteúdo para CSV"""
        try:
            if not conteudo or conteudo.strip() == "":
                raise ValueError("Nenhum conteúdo para exportar")
            
            tipo = kwargs.get("tipo", "generico")
            nome_arquivo = self._gerar_nome_arquivo(titulo, "csv")
            caminho = self.pasta_destino / nome_arquivo
            
            if tipo == "utilizadores":
                self._exportar_utilizadores(conteudo, caminho)
            elif tipo == "eventos":
                self._exportar_eventos(conteudo, caminho)
            else:
                self._exportar_generico(conteudo, caminho)
            
            self.ultimo_arquivo = caminho
            self._abrir_arquivo(caminho)
            return caminho
            
        except Exception as e:
            print(f"ERRO ao exportar CSV: {e}")
            traceback.print_exc()
            raise
    
    def _exportar_generico(self, conteudo, caminho):
        """Exporta conteúdo genérico"""
        linhas = conteudo.split("\n")
        
        with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_ALL)
            writer.writerow(["Conteudo"])
            
            for linha in linhas:
                linha = linha.strip()
                if linha and not linha.startswith("=") and not linha.startswith("-"):
                    linha_clean = (
                        linha.replace("[ATIVO]", "")
                        .replace("[DESATIVADO]", "")
                        .replace("[EXCLUIDO]", "")
                        .strip()
                    )
                    if linha_clean:
                        writer.writerow([linha_clean])
    
    def _exportar_utilizadores(self, conteudo, caminho):
        """Exporta dados de utilizadores"""
        linhas = conteudo.split("\n")
        dados_tabela = []
        cabecalho = ["#", "Utilizador", "Status", "Eventos", "Ultimo_Evento", "Modulos"]
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
        
        with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_ALL)
            writer.writerow(cabecalho)
            for linha in dados_tabela:
                writer.writerow(linha)
    
    def _exportar_eventos(self, conteudo, caminho):
        """Exporta eventos para CSV"""
        linhas = conteudo.split("\n")
        dados_tabela = []
        
        for linha in linhas:
            if "|" in linha and any(p in linha for p in ["ID", "Data", "Status", "Modulo"]):
                continue
            if "|" in linha:
                partes = [p.strip() for p in linha.split("|") if p.strip()]
                if len(partes) >= 4:
                    dados_tabela.append(partes)
        
        with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_ALL)
            writer.writerow(["ID", "Data/Hora", "Status", "Modulo", "Observacao", "Utilizador"])
            for linha in dados_tabela:
                writer.writerow(linha)


# ============================================================
# EXPORTADOR PDF (Herda de ExportadorBase)
# ============================================================

class ExportadorPDF(ExportadorBase):
    """Exporta relatórios para PDF usando ReportLab"""
    
    def exportar(self, conteudo, titulo, **kwargs):
        """Exporta conteúdo para PDF"""
        if not REPORTLAB_DISPONIVEL:
            raise ImportError("ReportLab não está instalado. Execute: pip install reportlab")
        
        try:
            if not conteudo or conteudo.strip() == "":
                raise ValueError("Nenhum conteúdo para exportar")
            
            estilo = kwargs.get("estilo", "padrao")
            nome_arquivo = self._gerar_nome_arquivo(titulo, "pdf")
            caminho = self.pasta_destino / nome_arquivo
            
            if estilo == "analitico":
                self._exportar_analitico(conteudo, titulo, caminho)
            elif estilo == "consulta":
                self._exportar_consulta(conteudo, titulo, caminho)
            else:
                self._exportar_padrao(conteudo, titulo, caminho)
            
            self.ultimo_arquivo = caminho
            self._abrir_arquivo(caminho)
            return caminho
            
        except Exception as e:
            print(f"ERRO ao exportar PDF: {e}")
            traceback.print_exc()
            raise
    
    def _criar_estilos_pdf(self):
        """Cria os estilos para o PDF"""
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
        """Exporta PDF com estilo padrão"""
        doc = SimpleDocTemplate(
            str(caminho),
            pagesize=landscape(A4),
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
        )
        
        story = []
        estilos = self._criar_estilos_pdf()
        
        # Cabeçalho
        cabecalho = Drawing(720, 60)
        cabecalho.add(Rect(0, 0, 720, 60, fillColor=HexColor("#eaf2f8"), 
                           strokeColor=HexColor("#1a5276"), strokeWidth=1))
        story.append(cabecalho)
        story.append(Spacer(1, -55))
        
        story.append(Paragraph("SISTEMA INTEGRADO DE SEGURANCA", estilos["titulo"]))
        story.append(Paragraph(titulo, estilos["subtitulo"]))
        
        linha = Drawing(720, 4)
        linha.add(Line(150, 2, 570, 2, strokeColor=HexColor("#1a5276"), strokeWidth=2))
        story.append(linha)
        story.append(Spacer(1, 10))
        
        # Conteúdo
        for linha_texto in conteudo.split("\n"):
            linha_texto = linha_texto.rstrip()
            if not linha_texto.strip():
                story.append(Spacer(1, 3))
                continue
            if linha_texto.strip().startswith("=") or linha_texto.strip().startswith("-"):
                continue
            story.append(Paragraph(linha_texto, estilos["normal"]))
            story.append(Spacer(1, 2))
        
        # Rodapé
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
    
    def _exportar_analitico(self, conteudo, titulo, caminho):
        """Exporta PDF com estilo analítico"""
        # Implementação similar ao método _exportar_padrao com ajustes específicos
        self._exportar_padrao(conteudo, titulo, caminho)
    
    def _exportar_consulta(self, conteudo, titulo, caminho):
        """Exporta PDF com estilo consulta"""
        self._exportar_padrao(conteudo, titulo, caminho)


# ============================================================
# FUNÇÃO DE EXPORTAÇÃO SIMPLIFICADA
# ============================================================

def exportar_relatorio(conteudo, titulo, tipo="pdf", **kwargs):
    """Função simplificada para exportar relatórios"""
    if tipo.lower() == "pdf":
        exportador = ExportadorPDF()
        return exportador.exportar(conteudo, titulo, **kwargs)
    elif tipo.lower() == "csv":
        exportador = ExportadorCSV()
        return exportador.exportar(conteudo, titulo, **kwargs)
    else:
        raise ValueError(f"Tipo de exportação inválido: {tipo}")