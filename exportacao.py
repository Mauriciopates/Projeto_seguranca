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
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, white, whitesmoke
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.graphics.shapes import Drawing, Line, Rect
    REPORTLAB_DISPONIVEL = True
    print("[INFO] ReportLab disponível")
except ImportError:
    REPORTLAB_DISPONIVEL = False
    print("[AVISO] ReportLab não instalado. Execute: pip install reportlab")

# ============================================================
# VERIFICA DISPONIBILIDADE DO MATPLOTLIB
# ============================================================

try:
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    MATPLOTLIB_DISPONIVEL = True
    print("[INFO] Matplotlib disponível")
except ImportError:
    MATPLOTLIB_DISPONIVEL = False
    print("[AVISO] Matplotlib não instalado. Execute: pip install matplotlib")

# ============================================================
# TESTE DO MATPLOTLIB
# ============================================================

def testar_matplotlib():
    try:
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib.figure import Figure
        import tempfile
        import os
        
        fig = Figure(figsize=(5, 3))
        ax = fig.add_subplot(111)
        ax.bar(['A', 'B', 'C'], [1, 2, 3])
        ax.set_title('Teste')
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            fig.savefig(tmp.name, format='png')
            tmp_path = tmp.name
        
        os.unlink(tmp_path)
        return True
    except Exception as e:
        print(f"[TESTE] ERRO no matplotlib: {e}")
        return False

if MATPLOTLIB_DISPONIVEL:
    testar_matplotlib()


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
# FUNÇÃO: exportar_csv_dados()
# ============================================================

def exportar_csv_dados(eventos, titulo, tipo="eventos", separador=None):
    try:
        if not eventos:
            raise ValueError("Nenhum evento para exportar")
        
        if separador is None:
            separador = perguntar_separador()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sep_nome = "ponto_virgula" if separador == ";" else "virgula"
        titulo_limpo = titulo.replace(" ", "_").replace("-", "_").lower()
        titulo_limpo = re.sub(r"[^a-zA-Z0-9_]", "", titulo_limpo)
        nome_arquivo = f"{titulo_limpo}_{sep_nome}_{timestamp}.csv"
        caminho = PASTA_RELATORIOS / nome_arquivo
        
        if tipo == "utilizadores":
            cabecalho = ["#", "Utilizador", "Status", "Eventos", "Ultimo_Evento", "Modulos"]
            dados = _extrair_dados_utilizadores(eventos)
        else:
            cabecalho = ["ID", "Data/Hora", "Status", "Modulo", "Observacao", "Utilizador"]
            dados = _extrair_dados_eventos(eventos)
        
        if not dados:
            raise ValueError("Nenhum dado para exportar")
        
        with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=separador, quoting=csv.QUOTE_ALL)
            writer.writerow(cabecalho)
            for linha in dados:
                writer.writerow(linha)
        
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
# FUNÇÃO: exportar_relatorio()
# ============================================================

def exportar_relatorio(conteudo, titulo, tipo="pdf", **kwargs):
    dados_brutos = kwargs.get("dados_brutos", None)
    tipo_dados = kwargs.get("tipo_dados", "eventos")
    separador = kwargs.get("separador", None)
    estilo = kwargs.get("estilo", "padrao")
    
    if tipo.lower() == "pdf":
        exportador = ExportadorPDF()
        return exportador.exportar(conteudo, titulo, estilo=estilo, **kwargs)
    
    elif tipo.lower() == "csv":
        if dados_brutos is not None:
            return exportar_csv_dados(dados_brutos, titulo, tipo=tipo_dados, separador=separador)
        else:
            exportador = ExportadorCSV()
            return exportador.exportar(conteudo, titulo, **kwargs)
    
    else:
        raise ValueError(f"Tipo de exportação inválido: {tipo}")


# ============================================================
# CLASSE BASE: ExportadorBase
# ============================================================

class ExportadorBase:
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
# EXPORTADOR CSV
# ============================================================

class ExportadorCSV(ExportadorBase):
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
# EXPORTADOR PDF - VERSÃO COMPLETA COM DETECÇÃO AUTOMÁTICA
# ============================================================

class ExportadorPDF(ExportadorBase):
    def exportar(self, conteudo, titulo, **kwargs):
        if not REPORTLAB_DISPONIVEL:
            raise ImportError("ReportLab não está instalado. Execute: pip install reportlab")
        
        try:
            if not conteudo or conteudo.strip() == "":
                raise ValueError("Nenhum conteúdo para exportar")
            
            estilo = kwargs.get("estilo", "padrao")
            
            # ============================================================
            # DETECÇÃO AUTOMÁTICA POR TÍTULO (MAIS ROBUSTA)
            # ============================================================
            titulo_upper = titulo.upper()
            
            # Se for Relatório de Utilizadores
            if "UTILIZADORES" in titulo_upper or "RELATORIO DE UTILIZADORES" in titulo_upper:
                estilo = "utilizadores"
                print(f"[INFO] Detectado Relatório de Utilizadores. Usando estilo 'utilizadores'")
            
            # Se for Relatório Analítico (contém "ANALITICO" no título)
            elif "ANALITICO" in titulo_upper or "RELATORIO ANALITICO" in titulo_upper:
                estilo = "analitico"
                print(f"[INFO] Detectado Relatório Analítico. Usando estilo 'analitico'")
            
            # Se for Detalhamento
            elif "DETALHAMENTO" in titulo_upper or "DETALHAMENTO DE EVENTOS" in titulo_upper:
                estilo = "detalhamento"
                print(f"[INFO] Detectado Detalhamento. Usando estilo 'detalhamento'")
            
            nome_arquivo = self._gerar_nome_arquivo(titulo, "pdf")
            caminho = self.pasta_destino / nome_arquivo
            
            print(f"\n[INFO] Exportando PDF com estilo: {estilo}")
            print(f"[INFO] Título: {titulo}")
            print(f"[INFO] Caminho: {caminho}")
            
            if estilo == "analitico":
                self._exportar_analitico(conteudo, titulo, caminho)
            elif estilo == "consulta":
                self._exportar_consulta(conteudo, titulo, caminho)
            elif estilo == "detalhamento":
                self._exportar_detalhamento_com_tabela(conteudo, titulo, caminho)
            elif estilo == "utilizadores":
                self._exportar_utilizadores_com_tabela(conteudo, titulo, caminho)
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
        
        estilo_secao = ParagraphStyle(
            "Secao",
            parent=styles["Normal"],
            fontSize=9,
            alignment=TA_LEFT,
            textColor=cor_primaria,
            fontName="Helvetica-Bold",
            leading=12,
        )
        
        return {
            "titulo": estilo_titulo,
            "subtitulo": estilo_subtitulo,
            "normal": estilo_normal,
            "rodape": estilo_rodape,
            "secao": estilo_secao,
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
    
    # ============================================================
    # _exportar_analitico() - VERSÃO COM MELHORIAS ESTÉTICAS
    # ============================================================
    
    def _exportar_analitico(self, conteudo, titulo, caminho):
        """
        Exporta PDF com estilo analítico e gráficos - LAYOUT DASHBOARD PROFISSIONAL
        """
        print("\n" + "=" * 60)
        print("[INFO] INICIANDO EXPORTAÇÃO ANALÍTICA")
        print("=" * 60)
        
        # Verifica se matplotlib está disponível
        if not MATPLOTLIB_DISPONIVEL:
            print("[ERRO] Matplotlib NÃO está disponível!")
            print("[INFO] Usando fallback para estilo padrão")
            self._exportar_padrao(conteudo, titulo, caminho)
            return
        
        print("[INFO] Matplotlib está disponível")
        
        # Cria um arquivo temporário que será mantido durante todo o processo
        import tempfile
        import os
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import io
        
        # Nome do arquivo temporário - será mantido até o PDF ser construído
        tmp_path = None
        
        try:
            from core import estado_sistema
            
            print(f"[INFO] estado_sistema: {estado_sistema is not None}")
            if estado_sistema:
                print(f"[INFO] Eventos: {len(estado_sistema.events) if hasattr(estado_sistema, 'events') else 0}")
            
            # ============================================================
            # EXTRAI DADOS PARA OS GRÁFICOS
            # ============================================================
            critical = 0
            warning = 0
            info = 0
            modulos = {}
            
            # Tenta extrair do estado_sistema
            if estado_sistema and hasattr(estado_sistema, 'events') and estado_sistema.events:
                print(f"[INFO] Extraindo dados de {len(estado_sistema.events)} eventos...")
                for evento in estado_sistema.events:
                    if hasattr(evento, 'payload') and isinstance(evento.payload, dict):
                        payload = evento.payload
                        sev = payload.get("severidade", "INFO")
                        if sev == "CRITICAL":
                            critical += 1
                        elif sev == "WARNING":
                            warning += 1
                        else:
                            info += 1
                        
                        modulo = payload.get("modulo", "DESCONHECIDO")
                        modulos[modulo] = modulos.get(modulo, 0) + 1
            
            # Fallback: extrai do conteúdo
            if critical == 0 and warning == 0 and info == 0:
                print("[INFO] estado_sistema vazio. Extraindo do conteúdo...")
                critical, warning, info, modulos = self._extrair_dados_do_texto_analitico(conteudo)
            
            total = critical + warning + info
            print(f"[INFO] Dados: Total={total}, CRITICAL={critical}, WARNING={warning}, INFO={info}")
            
            if total == 0:
                print("[AVISO] Nenhum dado para gerar gráficos!")
                self._exportar_padrao(conteudo, titulo, caminho)
                return
            
            # ============================================================
            # CRIA OS GRÁFICOS COM MATPLOTLIB - LAYOUT DASHBOARD PROFISSIONAL
            # ============================================================
            print("[INFO] Criando gráficos estilo dashboard profissional...")
            
            # Configuração do estilo
            plt.rcParams['font.size'] = 10
            plt.rcParams['axes.titlesize'] = 12
            plt.rcParams['axes.titleweight'] = 'bold'
            
            # Cria figura com 2 gráficos lado a lado
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            fig.patch.set_facecolor('#f8f9fa')
            fig.suptitle('ANÁLISE DE SEGURANÇA', fontsize=14, fontweight='bold', color='#1a5276', y=0.98)
            
            # ============================================================
            # GRÁFICO 1: PIZZA - Distribuição por Severidade
            # ============================================================
            labels = []
            sizes = []
            colors = []
            explode = []
            
            if critical > 0:
                labels.append('CRITICAL')
                sizes.append(critical)
                colors.append('#dc3545')
                explode.append(0.05)
            if warning > 0:
                labels.append('WARNING')
                sizes.append(warning)
                colors.append('#ffc107')
                explode.append(0.05)
            if info > 0:
                labels.append('INFO')
                sizes.append(info)
                colors.append('#17a2b8')
                explode.append(0.05)
            
            if sizes:
                wedges, texts, autotexts = ax1.pie(
                    sizes, 
                    labels=labels, 
                    autopct=lambda pct: f'{pct:.1f}%\n({int(pct/100*total) if total > 0 else 0})',
                    colors=colors,
                    explode=explode,
                    startangle=90,
                    shadow=True,
                    textprops={'fontsize': 11, 'color': '#2c3e50'},
                    pctdistance=0.75,
                    labeldistance=1.15
                )
                
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                    autotext.set_fontsize(10)
                
                ax1.set_title(f'Eventos por Severidade\nTotal: {total} eventos', 
                             fontsize=13, fontweight='bold', color='#1a5276', pad=20)
            
            # ============================================================
            # GRÁFICO 2: BARRAS - Eventos por Módulo
            # ============================================================
            if modulos:
                modulos_ordenados = sorted(modulos.items(), key=lambda x: x[1], reverse=True)[:8]
                nomes = [m[:15] + '...' if len(m) > 15 else m for m, _ in modulos_ordenados]
                valores = [v for _, v in modulos_ordenados]
                
                cores_barras = ['#2c3e50', '#34495e', '#5d6d7e', '#85c1e9', 
                               '#5dade2', '#3498db', '#2980b9', '#1a5276']
                
                bars = ax2.bar(nomes, valores, color=cores_barras[:len(nomes)], 
                              edgecolor='white', linewidth=1.5, alpha=0.9)
                
                for bar, valor in zip(bars, valores):
                    height = bar.get_height()
                    ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                            f'{valor}', ha='center', va='bottom', 
                            fontsize=10, fontweight='bold', color='#2c3e50')
                
                ax2.set_title('Eventos por Módulo', fontsize=13, fontweight='bold', color='#1a5276', pad=20)
                ax2.set_ylabel('Quantidade de Eventos', fontsize=11, color='#2c3e50')
                ax2.tick_params(axis='x', rotation=30, labelsize=10)
                ax2.tick_params(axis='y', labelsize=10)
                ax2.grid(axis='y', alpha=0.3, linestyle='--', color='#bdc3c7')
                ax2.set_axisbelow(True)
                
                ax2.spines['top'].set_visible(False)
                ax2.spines['right'].set_visible(False)
                ax2.spines['left'].set_color('#bdc3c7')
                ax2.spines['bottom'].set_color('#bdc3c7')
            
            plt.tight_layout()
            
            # ============================================================
            # SALVA O GRÁFICO EM ARQUIVO TEMPORÁRIO
            # ============================================================
            print("[INFO] Salvando gráfico em arquivo temporário...")
            
            # Cria um arquivo temporário com nome único
            import tempfile
            import os
            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.png', prefix='grafico_')
            os.close(tmp_fd)
            
            # Salva a figura no arquivo
            fig.savefig(tmp_path, format='png', dpi=150, bbox_inches='tight', 
                       facecolor='#f8f9fa', edgecolor='none')
            
            print(f"[INFO] Gráfico salvo em: {tmp_path}")
            print(f"[INFO] Tamanho: {os.path.getsize(tmp_path)} bytes")
            
            # Fecha a figura para liberar memória
            plt.close(fig)
            
            # ============================================================
            # CRIA O PDF COM DESIGN PROFISSIONAL
            # ============================================================
            print("[INFO] Criando PDF com design profissional...")
            from reportlab.platypus import Image as ReportLabImage
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import cm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.graphics.shapes import Drawing, Line, Rect
            from reportlab.lib.colors import white, HexColor as HexColorLib
            from reportlab.lib.styles import ParagraphStyle
            
            doc = SimpleDocTemplate(
                str(caminho),
                pagesize=A4,
                topMargin=2 * cm,
                bottomMargin=2 * cm,
                leftMargin=2 * cm,
                rightMargin=2 * cm,
            )
            
            story = []
            estilos = self._criar_estilos_pdf()
            
            # ============================================================
            # CABECALHO PERSONALIZADO
            # ============================================================
            # Título principal com fundo
            story.append(Spacer(1, 0.5))
            
            # Linha decorativa superior
            linha_superior = Drawing(720, 6)
            linha_superior.add(Rect(0, 0, 720, 6, fillColor=HexColorLib("#1a5276"), strokeColor=None))
            story.append(linha_superior)
            story.append(Spacer(1, 8))
            
            # Título principal
            story.append(Paragraph("SISTEMA INTEGRADO DE SEGURANCA", estilos["titulo"]))
            story.append(Spacer(1, 2))
            story.append(Paragraph("RELATORIO ANALITICO", estilos["subtitulo"]))
            story.append(Spacer(1, 8))
            
            # Linha decorativa central
            linha = Drawing(720, 4)
            linha.add(Line(150, 2, 570, 2, strokeColor=HexColorLib("#1a5276"), strokeWidth=2))
            story.append(linha)
            story.append(Spacer(1, 8))
            
            # ============================================================
            # INSERE O GRÁFICO
            # ============================================================
            try:
                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                    print(f"[INFO] Inserindo gráfico no PDF...")
                    img = ReportLabImage(tmp_path, width=17*cm, height=8*cm)
                    story.append(img)
                    story.append(Spacer(1, 10))
                    print("[INFO] Gráfico inserido com sucesso!")
                else:
                    print(f"[ERRO] Arquivo de imagem inválido: {tmp_path}")
            except Exception as e:
                print(f"[ERRO] Falha ao inserir gráfico: {e}")
                traceback.print_exc()
            
            # ============================================================
            # SEÇÃO: RESUMO NUMÉRICO (COM ESTILO)
            # ============================================================
            # Título da seção com destaque
            estilo_secao_destaque = ParagraphStyle(
                "SecaoDestaque",
                parent=estilos["normal"],
                fontSize=12,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
                textColor=HexColorLib("#1a5276"),
                leading=16,
                spaceAfter=6,
            )
            
            story.append(Paragraph("═" * 50, estilos["normal"]))
            story.append(Paragraph("RESUMO NUMÉRICO", estilo_secao_destaque))
            story.append(Paragraph("═" * 50, estilos["normal"]))
            story.append(Spacer(1, 6))
            
            # Dados para a tabela de resumo
            dados_resumo = [
                ["Métrica", "Valor", "Percentual"],
                ["Total de Eventos", str(total), "100%"],
                ["CRITICAL", str(critical), f"{critical/total*100:.1f}%" if total > 0 else "0%"],
                ["WARNING", str(warning), f"{warning/total*100:.1f}%" if total > 0 else "0%"],
                ["INFO", str(info), f"{info/total*100:.1f}%" if total > 0 else "0%"],
            ]
            
            from reportlab.platypus import Table, TableStyle
            
            tabela_resumo = Table(dados_resumo, colWidths=[4*cm, 3*cm, 3*cm])
            tabela_resumo.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColorLib("#1a5276")),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColorLib("#f0f4fa"), white]),
                ('GRID', (0, 0), (-1, -1), 0.5, HexColorLib("#b0c4d8")),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            
            story.append(tabela_resumo)
            story.append(Spacer(1, 10))
            
            # ============================================================
            # SEÇÃO: DISTRIBUIÇÃO POR MÓDULO
            # ============================================================
            if modulos:
                story.append(Paragraph("═" * 50, estilos["normal"]))
                story.append(Paragraph("DISTRIBUIÇÃO POR MÓDULO", estilo_secao_destaque))
                story.append(Paragraph("═" * 50, estilos["normal"]))
                story.append(Spacer(1, 4))
                
                estilo_modulo = ParagraphStyle(
                    "ModuloTexto",
                    parent=estilos["normal"],
                    fontSize=10,
                    alignment=TA_LEFT,
                    fontName="Helvetica",
                    textColor=HexColorLib("#2c3e50"),
                    leading=14,
                )
                
                # Cria uma tabela para os módulos (2 colunas)
                dados_modulos = [["Módulo", "Eventos"]]
                for modulo, qtd in sorted(modulos.items(), key=lambda x: x[1], reverse=True)[:10]:
                    pct = qtd/total*100 if total > 0 else 0
                    dados_modulos.append([modulo, f"{qtd} ({pct:.1f}%)"])
                
                # Adiciona mais linhas vazias se necessário
                while len(dados_modulos) < 6:
                    dados_modulos.append(["", ""])
                
                tabela_modulos = Table(dados_modulos, colWidths=[5*cm, 4*cm])
                tabela_modulos.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColorLib("#2980b9")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColorLib("#f0f4fa"), white]),
                    ('GRID', (0, 0), (-1, -1), 0.5, HexColorLib("#b0c4d8")),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ]))
                
                story.append(tabela_modulos)
                story.append(Spacer(1, 10))
            
            # ============================================================
            # SEÇÃO: DETALHAMENTO DOS EVENTOS
            # ============================================================
            story.append(Paragraph("═" * 50, estilos["normal"]))
            story.append(Paragraph("DETALHAMENTO DOS EVENTOS", estilo_secao_destaque))
            story.append(Paragraph("═" * 50, estilos["normal"]))
            story.append(Spacer(1, 6))
            
            # Processa o conteúdo (limita para não ficar muito grande)
            linhas = conteudo.split("\n")
            contador = 0
            for linha in linhas:
                if contador > 80:
                    story.append(Paragraph("... (continuação do relatório omitida)", estilos["normal"]))
                    break
                linha = linha.rstrip()
                if not linha.strip():
                    story.append(Spacer(1, 2))
                    continue
                
                if linha.strip().startswith("=") or linha.strip().startswith("--") or linha.strip().startswith("-"):
                    story.append(Paragraph(linha, estilos["secao"]))
                else:
                    story.append(Paragraph(linha, estilos["normal"]))
                    story.append(Spacer(1, 1))
                contador += 1
            
            # ============================================================
            # RODAPE
            # ============================================================
            story.append(Spacer(1, 15))
            
            # Linha decorativa inferior
            linha_inferior = Drawing(720, 4)
            linha_inferior.add(Line(0, 2, 720, 2, strokeColor=HexColorLib("#1a5276"), strokeWidth=1.5))
            story.append(linha_inferior)
            story.append(Spacer(1, 4))
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            story.append(Paragraph(
                "Relatório gerado automaticamente pelo Sistema Integrado de Segurança",
                estilos["rodape"]
            ))
            story.append(Paragraph(
                f"Documento: REL-{datetime.now().strftime('%Y%m%d')}-{timestamp[-4:]} | Versão: 1.0",
                estilos["rodape"]
            ))
            
            # ============================================================
            # CONSTRÓI O PDF
            # ============================================================
            print("[INFO] Construindo o PDF...")
            doc.build(story)
            
            print(f"[INFO] PDF gerado com sucesso: {caminho}")
            print("=" * 60 + "\n")
            
        except Exception as e:
            print(f"[ERRO] Falha ao gerar PDF analítico: {e}")
            traceback.print_exc()
            print("[INFO] Usando fallback para estilo padrão")
            self._exportar_padrao(conteudo, titulo, caminho)
        
        finally:
            # ============================================================
            # LIMPA ARQUIVO TEMPORÁRIO
            # ============================================================
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                    print("[INFO] Arquivo temporário removido")
                except:
                    pass
    
    # ============================================================
    # _extrair_dados_do_texto_analitico() - AUXILIAR
    # ============================================================
    
    def _extrair_dados_do_texto_analitico(self, conteudo):
        critical = 0
        warning = 0
        info = 0
        modulos = {}
        
        linhas = conteudo.split("\n")
        em_modulos = False
        import re
        
        for linha in linhas:
            linha = linha.strip()
            
            if "MODULOS ENCONTRADOS" in linha.upper():
                em_modulos = True
                continue
            
            if em_modulos and (linha.startswith("---") or linha.startswith("==") or "UTILIZADORES" in linha.upper()):
                em_modulos = False
                continue
            
            if em_modulos and ":" in linha and "eventos" in linha.lower():
                try:
                    partes = linha.split(":")
                    if len(partes) == 2:
                        nome_modulo = partes[0].strip()
                        numeros = re.findall(r'\d+', partes[1])
                        if numeros:
                            qtd = int(numeros[0])
                            modulos[nome_modulo] = qtd
                except:
                    pass
            
            if "CRITICAL:" in linha.upper():
                try:
                    numeros = re.findall(r'\d+', linha)
                    if numeros:
                        critical = int(numeros[0])
                except:
                    pass
            
            if "WARNING:" in linha.upper():
                try:
                    numeros = re.findall(r'\d+', linha)
                    if numeros:
                        warning = int(numeros[0])
                except:
                    pass
            
            if "INFO:" in linha.upper() and "WARNING" not in linha.upper():
                try:
                    numeros = re.findall(r'\d+', linha)
                    if numeros:
                        info = int(numeros[0])
                except:
                    pass
        
        return critical, warning, info, modulos
    
    # ============================================================
    # _exportar_utilizadores_com_tabela() - FUNCIONANDO
    # ============================================================
    
    def _exportar_utilizadores_com_tabela(self, conteudo, titulo, caminho):
        """
        Exporta PDF do Relatório de Utilizadores com TABELA formatada
        """
        from reportlab.platypus import Table, TableStyle, Paragraph
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.lib.styles import ParagraphStyle
        
        print("[INFO] Gerando Relatório de Utilizadores com tabela...")
        
        # ============================================================
        # CONFIGURAÇÕES DE ESTILO
        # ============================================================
        COR_PRIMARIA = HexColor("#1a5276")
        COR_FUNDO_CABECALHO = HexColor("#1a5276")
        COR_FUNDO_LINHA_PAR = HexColor("#f0f4fa")
        COR_FUNDO_LINHA_IMPAR = HexColor("#ffffff")
        COR_BORDA = colors.grey
        
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
        
        # ============================================================
        # CABECALHO
        # ============================================================
        story.append(Paragraph("SISTEMA INTEGRADO DE SEGURANCA", estilos["titulo"]))
        story.append(Spacer(1, 4))
        story.append(Paragraph("RELATORIO DE UTILIZADORES", estilos["subtitulo"]))
        story.append(Spacer(1, 8))
        
        linha = Drawing(720, 4)
        linha.add(Line(150, 2, 570, 2, strokeColor=COR_PRIMARIA, strokeWidth=2))
        story.append(linha)
        story.append(Spacer(1, 10))
        
        # ============================================================
        # EXTRAI DADOS DO CONTEÚDO
        # ============================================================
        total_utilizadores = 0
        ativos = 0
        desativados = 0
        excluidos = 0
        eventos_periodo = 0
        
        linhas = conteudo.split("\n")
        import re
        
        for linha in linhas:
            linha = linha.strip()
            if "Total de utilizadores" in linha:
                numeros = re.findall(r'\d+', linha)
                if numeros:
                    total_utilizadores = int(numeros[0])
            if "Ativos:" in linha:
                numeros = re.findall(r'\d+', linha)
                if numeros:
                    ativos = int(numeros[0])
            if "Desativados:" in linha:
                numeros = re.findall(r'\d+', linha)
                if numeros:
                    desativados = int(numeros[0])
            if "Excluídos:" in linha or "Excluidos:" in linha:
                numeros = re.findall(r'\d+', linha)
                if numeros:
                    excluidos = int(numeros[0])
            if "Eventos no período:" in linha:
                numeros = re.findall(r'\d+', linha)
                if numeros:
                    eventos_periodo = int(numeros[0])
        
        # ============================================================
        # ADICIONA O RESUMO
        # ============================================================
        resumo_texto = []
        if total_utilizadores > 0:
            resumo_texto.append(f"Total: {total_utilizadores} utilizadores")
        if eventos_periodo > 0:
            resumo_texto.append(f"Eventos: {eventos_periodo}")
        if ativos > 0:
            resumo_texto.append(f"Ativos: {ativos}")
        if desativados > 0:
            resumo_texto.append(f"Desativados: {desativados}")
        if excluidos > 0:
            resumo_texto.append(f"Excluídos: {excluidos}")
        
        estilo_resumo = ParagraphStyle(
            "ResumoPersonalizado",
            parent=estilos["normal"],
            fontSize=10,
            alignment=TA_LEFT,
            textColor=COR_PRIMARIA,
            fontName="Helvetica-Bold",
            leading=14,
            spaceAfter=8,
        )
        
        resumo_completo = "   |   ".join(resumo_texto)
        story.append(Paragraph(resumo_completo, estilo_resumo))
        story.append(Spacer(1, 10))
        
        # ============================================================
        # PREPARA OS DADOS DA TABELA
        # ============================================================
        
        estilo_celula = ParagraphStyle(
            "CelulaTexto",
            parent=estilos["normal"],
            fontSize=7,
            alignment=TA_LEFT,
            fontName="Helvetica",
            leading=9,
        )
        
        estilo_celula_center = ParagraphStyle(
            "CelulaCenter",
            parent=estilos["normal"],
            fontSize=7,
            alignment=TA_CENTER,
            fontName="Helvetica",
            leading=9,
        )
        
        estilo_cabecalho = ParagraphStyle(
            "CabecalhoTexto",
            parent=estilos["normal"],
            fontSize=8,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            textColor=colors.whitesmoke,
            leading=10,
        )
        
        cabecalho_tabela = [
            Paragraph("#", estilo_cabecalho),
            Paragraph("Utilizador", estilo_cabecalho),
            Paragraph("Status", estilo_cabecalho),
            Paragraph("Eventos", estilo_cabecalho),
            Paragraph("Ultimo Evento", estilo_cabecalho),
            Paragraph("Modulos", estilo_cabecalho),
        ]
        
        dados_tabela = [cabecalho_tabela]
        
        # ============================================================
        # EXTRAI DADOS DA TABELA DO CONTEÚDO
        # ============================================================
        em_tabela = False
        
        for linha in linhas:
            linha = linha.strip()
            if not linha:
                continue
            
            if "|" in linha and "#" in linha and "Utilizador" in linha:
                em_tabela = True
                continue
            
            if em_tabela and (linha.startswith("Dica:") or linha.startswith("LEGENDA") or linha.startswith("=")):
                em_tabela = False
                continue
            
            if em_tabela and "|" in linha:
                linha_clean = linha
                if linha_clean.startswith("|"):
                    linha_clean = linha_clean[1:]
                if linha_clean.endswith("|"):
                    linha_clean = linha_clean[:-1]
                
                partes = [p.strip() for p in linha_clean.split("|")]
                
                if len(partes) >= 6:
                    status = partes[2] if len(partes) > 2 else ""
                    status = status.replace("[", "").replace("]", "")
                    
                    utilizador = partes[1] if len(partes) > 1 else ""
                    if len(utilizador) > 20:
                        utilizador = utilizador[:18] + "..."
                    
                    modulos = partes[5] if len(partes) > 5 else ""
                    if len(modulos) > 25:
                        modulos = modulos[:23] + "..."
                    
                    linha_dados = [
                        Paragraph(partes[0] if len(partes) > 0 else "", estilo_celula_center),
                        Paragraph(utilizador, estilo_celula),
                        Paragraph(status, estilo_celula_center),
                        Paragraph(partes[3] if len(partes) > 3 else "", estilo_celula_center),
                        Paragraph(partes[4] if len(partes) > 4 else "", estilo_celula_center),
                        Paragraph(modulos, estilo_celula),
                    ]
                    dados_tabela.append(linha_dados)
        
        # ============================================================
        # ADICIONA A TABELA
        # ============================================================
        if len(dados_tabela) > 1:
            larguras = [1.0 * cm, 3.5 * cm, 2.0 * cm, 1.5 * cm, 2.5 * cm, 4.0 * cm]
            tabela = Table(dados_tabela, colWidths=larguras, repeatRows=1)
            
            estilo_tabela = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), COR_FUNDO_CABECALHO),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (2, -1), 'CENTER'),
                ('ALIGN', (3, 1), (3, -1), 'CENTER'),
                ('ALIGN', (4, 1), (4, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COR_FUNDO_LINHA_PAR, COR_FUNDO_LINHA_IMPAR]),
                ('GRID', (0, 0), (-1, -1), 0.5, COR_BORDA),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ])
            
            cores_status = {
                "ATIVO": HexColor("#2a8a4a"),
                "DESATIVADO": HexColor("#cc8800"),
                "EXCLUIDO": HexColor("#cc3333"),
            }
            
            for i in range(1, len(dados_tabela)):
                if len(dados_tabela[i]) > 2:
                    try:
                        status_text = dados_tabela[i][2].getPlainText() if hasattr(dados_tabela[i][2], 'getPlainText') else ""
                    except:
                        status_text = ""
                    for status in cores_status:
                        if status in status_text.upper():
                            estilo_tabela.add('TEXTCOLOR', (2, i), (2, i), cores_status[status])
                            break
            
            tabela.setStyle(estilo_tabela)
            story.append(tabela)
            
            story.append(Spacer(1, 10))
            estilo_contagem = ParagraphStyle(
                "Contagem",
                parent=estilos["normal"],
                fontSize=9,
                alignment=TA_LEFT,
                textColor=COR_PRIMARIA,
                fontName="Helvetica",
                leading=12,
            )
            story.append(Paragraph(
                f"Total de utilizadores exibidos: {len(dados_tabela) - 1}",
                estilo_contagem
            ))
        else:
            story.append(Paragraph("Nenhum utilizador encontrado.", estilos["normal"]))
        
        # ============================================================
        # LEGENDA
        # ============================================================
        story.append(Spacer(1, 10))
        estilo_legenda = ParagraphStyle(
            "Legenda",
            parent=estilos["normal"],
            fontSize=8,
            alignment=TA_LEFT,
            fontName="Helvetica",
            textColor=HexColor("#5d6d7e"),
            leading=11,
        )
        
        story.append(Paragraph("LEGENDA:", estilo_legenda))
        story.append(Paragraph("• [ATIVO] - Utilizador que aparece nos logs (tem eventos registados)", estilo_legenda))
        story.append(Paragraph("• [DESATIVADO] - Identificado por evento de desativacao no log", estilo_legenda))
        story.append(Paragraph("• [EXCLUIDO] - Identificado por evento de exclusao no log", estilo_legenda))
        
        # ============================================================
        # RODAPE
        # ============================================================
        story.append(Spacer(1, 15))
        linha_inferior = Drawing(720, 4)
        linha_inferior.add(Line(0, 2, 720, 2, strokeColor=COR_PRIMARIA, strokeWidth=1.5))
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
        print(f"[INFO] PDF do Relatório de Utilizadores gerado com sucesso: {caminho}")
    
    # ============================================================
    # _exportar_detalhamento_com_tabela() - FUNCIONANDO
    # ============================================================
    
    def _exportar_detalhamento_com_tabela(self, conteudo, titulo, caminho):
        from reportlab.platypus import Table, TableStyle, Paragraph
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.lib.styles import ParagraphStyle
        
        from core import estado_sistema
        
        COR_PRIMARIA = HexColor("#1a5276")
        COR_FUNDO_CABECALHO = HexColor("#1a5276")
        COR_FUNDO_LINHA_PAR = HexColor("#f0f4fa")
        COR_FUNDO_LINHA_IMPAR = HexColor("#ffffff")
        COR_BORDA = colors.grey
        
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
        
        story.append(Paragraph("SISTEMA INTEGRADO DE SEGURANCA", estilos["titulo"]))
        story.append(Spacer(1, 4))
        story.append(Paragraph(titulo, estilos["subtitulo"]))
        story.append(Spacer(1, 12))
        
        modulo_nome = titulo.replace("DETALHAMENTO DE EVENTOS POR MODULO - ", "").strip()
        
        eventos_modulo = []
        severidades = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
        utilizadores = set()
        
        if estado_sistema and hasattr(estado_sistema, 'events') and estado_sistema.events:
            for evento in estado_sistema.events:
                if hasattr(evento, 'payload') and isinstance(evento.payload, dict):
                    modulo_evento = evento.payload.get("modulo", "").upper()
                    if modulo_evento == modulo_nome:
                        eventos_modulo.append(evento)
                        sev = evento.payload.get("severidade", "INFO")
                        if sev in severidades:
                            severidades[sev] += 1
                        user = evento.payload.get("utilizador")
                        if user:
                            utilizadores.add(user)
        
        if not eventos_modulo:
            eventos_modulo = self._extrair_eventos_do_texto(conteudo)
        
        eventos_ordenados = sorted(eventos_modulo, key=lambda e: e.timestamp, reverse=True) if eventos_modulo else []
        
        resumo_texto = []
        resumo_texto.append(f"Total: {len(eventos_ordenados)} eventos")
        if severidades.get("CRITICAL", 0) > 0:
            resumo_texto.append(f"CRITICAL: {severidades['CRITICAL']}")
        if severidades.get("WARNING", 0) > 0:
            resumo_texto.append(f"WARNING: {severidades['WARNING']}")
        if severidades.get("INFO", 0) > 0:
            resumo_texto.append(f"INFO: {severidades['INFO']}")
        if utilizadores:
            resumo_texto.append(f"Utilizadores envolvidos: {len(utilizadores)}")
        
        estilo_resumo = ParagraphStyle(
            "ResumoPersonalizado",
            parent=estilos["normal"],
            fontSize=10,
            alignment=TA_LEFT,
            textColor=COR_PRIMARIA,
            fontName="Helvetica-Bold",
            leading=14,
            spaceAfter=8,
        )
        
        resumo_completo = "   |   ".join(resumo_texto)
        story.append(Paragraph(resumo_completo, estilo_resumo))
        story.append(Spacer(1, 10))
        
        estilo_celula = ParagraphStyle(
            "CelulaTexto",
            parent=estilos["normal"],
            fontSize=7,
            alignment=TA_LEFT,
            fontName="Helvetica",
            leading=9,
        )
        
        estilo_celula_center = ParagraphStyle(
            "CelulaCenter",
            parent=estilos["normal"],
            fontSize=7,
            alignment=TA_CENTER,
            fontName="Helvetica",
            leading=9,
        )
        
        estilo_cabecalho = ParagraphStyle(
            "CabecalhoTexto",
            parent=estilos["normal"],
            fontSize=8,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            textColor=colors.whitesmoke,
            leading=10,
        )
        
        cabecalho_tabela = [
            Paragraph("Data/Hora", estilo_cabecalho),
            Paragraph("Tipo", estilo_cabecalho),
            Paragraph("Descricao", estilo_cabecalho),
            Paragraph("Utilizador", estilo_cabecalho),
            Paragraph("Severidade", estilo_cabecalho),
        ]
        
        dados_tabela = [cabecalho_tabela]
        
        for evento in eventos_ordenados[:200]:
            if hasattr(evento, 'payload') and isinstance(evento.payload, dict):
                payload = evento.payload
                data_hora = evento.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                tipo = evento.event_type if hasattr(evento, 'event_type') else "EVENTO"
                descricao = payload.get("descricao", "") or "-"
                descricao = descricao.replace("'", "").strip()
                descricao = self._quebrar_descricao(descricao, 60)
                utilizador = payload.get("utilizador", "-") or "-"
                if utilizador and len(utilizador) > 20:
                    utilizador = utilizador[:18] + "..."
                severidade = payload.get("severidade", "INFO")
                
                linha = [
                    Paragraph(data_hora, estilo_celula_center),
                    Paragraph(tipo, estilo_celula_center),
                    Paragraph(descricao, estilo_celula),
                    Paragraph(utilizador, estilo_celula_center),
                    Paragraph(severidade, estilo_celula_center),
                ]
                dados_tabela.append(linha)
        
        if len(dados_tabela) > 1:
            larguras = [2.2 * cm, 1.8 * cm, 5.5 * cm, 2.0 * cm, 1.8 * cm]
            tabela = Table(dados_tabela, colWidths=larguras, repeatRows=1)
            
            estilo_tabela = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), COR_FUNDO_CABECALHO),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                ('ALIGN', (3, 1), (3, -1), 'CENTER'),
                ('ALIGN', (4, 1), (4, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COR_FUNDO_LINHA_PAR, COR_FUNDO_LINHA_IMPAR]),
                ('GRID', (0, 0), (-1, -1), 0.5, COR_BORDA),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ])
            
            cores_severidade = {
                "CRITICAL": HexColor("#cc3333"),
                "WARNING": HexColor("#cc8800"),
                "INFO": HexColor("#1a6c9a"),
            }
            
            for i in range(1, len(dados_tabela)):
                if len(dados_tabela[i]) > 4:
                    sev_text = eventos_ordenados[i-1].payload.get("severidade", "INFO") if i-1 < len(eventos_ordenados) else "INFO"
                    sev_upper = sev_text.upper()
                    if sev_upper in cores_severidade:
                        estilo_tabela.add('TEXTCOLOR', (4, i), (4, i), cores_severidade[sev_upper])
                        if sev_upper == "CRITICAL":
                            estilo_tabela.add('BACKGROUND', (4, i), (4, i), HexColor("#ffebee"))
                        elif sev_upper == "WARNING":
                            estilo_tabela.add('BACKGROUND', (4, i), (4, i), HexColor("#fff8e1"))
            
            tabela.setStyle(estilo_tabela)
            story.append(tabela)
            
            story.append(Spacer(1, 10))
            estilo_contagem = ParagraphStyle(
                "Contagem",
                parent=estilos["normal"],
                fontSize=9,
                alignment=TA_LEFT,
                textColor=COR_PRIMARIA,
                fontName="Helvetica",
                leading=12,
            )
            story.append(Paragraph(
                f"Total de eventos exibidos: {len(dados_tabela) - 1} (de {len(eventos_ordenados)} eventos no módulo)",
                estilo_contagem
            ))
        else:
            story.append(Paragraph("Nenhum evento encontrado para este módulo.", estilos["normal"]))
        
        story.append(Spacer(1, 20))
        linha_inferior = Drawing(720, 4)
        linha_inferior.add(Line(0, 2, 720, 2, strokeColor=COR_PRIMARIA, strokeWidth=1.5))
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
    
    # ============================================================
    # _quebrar_descricao() - AUXILIAR
    # ============================================================
    
    def _quebrar_descricao(self, descricao, limite=60):
        if not descricao or len(descricao) <= limite:
            return descricao
        
        palavras = descricao.split()
        linhas = []
        linha_atual = ""
        
        for palavra in palavras:
            if len(linha_atual) + len(palavra) + 1 <= limite:
                if linha_atual:
                    linha_atual += " " + palavra
                else:
                    linha_atual = palavra
            else:
                if linha_atual:
                    linhas.append(linha_atual)
                if len(palavra) > limite:
                    for i in range(0, len(palavra), limite):
                        linhas.append(palavra[i:i+limite])
                    linha_atual = ""
                else:
                    linha_atual = palavra
        
        if linha_atual:
            linhas.append(linha_atual)
        
        return "<br/>".join(linhas)
    
    # ============================================================
    # _extrair_eventos_do_texto() - FALLBACK
    # ============================================================
    
    def _extrair_eventos_do_texto(self, conteudo):
        eventos = []
        linhas = conteudo.split("\n")
        
        padrao = r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*$"
        
        for linha in linhas:
            linha = linha.strip()
            if not linha:
                continue
            match = re.match(padrao, linha)
            if match:
                try:
                    grupos = [g.strip() for g in match.groups()]
                    
                    class EventoSimulado:
                        def __init__(self, data, tipo, desc, user, sev):
                            try:
                                self.timestamp = datetime.strptime(data, "%Y-%m-%d %H:%M:%S")
                            except:
                                self.timestamp = datetime.now()
                            self.event_type = tipo
                            self.payload = {
                                "descricao": desc,
                                "utilizador": user if user != "-" else None,
                                "severidade": sev
                            }
                    
                    eventos.append(EventoSimulado(grupos[0], grupos[1], grupos[2], grupos[3], grupos[4]))
                except Exception as e:
                    continue
        
        return eventos
    
    # ============================================================
    # _exportar_consulta() - NOVA VERSÃO COM 10 ÚLTIMOS EVENTOS
    # ============================================================
    
    def _exportar_consulta(self, conteudo, titulo, caminho):
        """
        Exporta PDF da Consulta Geral do Sistema com os 10 últimos eventos
        """
        print("\n" + "=" * 60)
        print("[INFO] EXPORTANDO CONSULTA GERAL - PDF")
        print("=" * 60)
        
        try:
            from core import estado_sistema
            from reportlab.platypus import Table, TableStyle, Paragraph
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.graphics.shapes import Drawing, Line, Rect
            from reportlab.lib.colors import white, HexColor as HexColorLib
            
            # ============================================================
            # EXTRAI DADOS DO estado_sistema
            # ============================================================
            if not estado_sistema or not estado_sistema.events:
                print("[AVISO] Nenhum evento carregado. Usando fallback para estilo padrão.")
                self._exportar_padrao(conteudo, titulo, caminho)
                return
            
            eventos = estado_sistema.events
            
            # Estatísticas
            total = len(eventos)
            critical = 0
            warning = 0
            info = 0
            modulos = {}
            
            for evento in eventos:
                if hasattr(evento, 'payload') and isinstance(evento.payload, dict):
                    sev = evento.payload.get("severidade", "INFO")
                    if sev == "CRITICAL":
                        critical += 1
                    elif sev == "WARNING":
                        warning += 1
                    else:
                        info += 1
                    
                    modulo = evento.payload.get("modulo", "DESCONHECIDO")
                    modulos[modulo] = modulos.get(modulo, 0) + 1
            
            # Últimos 10 eventos (mais recentes primeiro)
            ultimos_eventos = sorted(eventos, key=lambda e: e.timestamp, reverse=True)[:10]
            
            # ============================================================
            # CRIA O PDF
            # ============================================================
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import cm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            
            doc = SimpleDocTemplate(
                str(caminho),
                pagesize=A4,
                topMargin=2 * cm,
                bottomMargin=2 * cm,
                leftMargin=2 * cm,
                rightMargin=2 * cm,
            )
            
            story = []
            estilos = self._criar_estilos_pdf()
            
            # ============================================================
            # CABECALHO
            # ============================================================
            # Linha decorativa superior
            linha_superior = Drawing(720, 6)
            linha_superior.add(Rect(0, 0, 720, 6, fillColor=HexColorLib("#1a5276"), strokeColor=None))
            story.append(linha_superior)
            story.append(Spacer(1, 8))
            
            story.append(Paragraph("SISTEMA INTEGRADO DE SEGURANCA", estilos["titulo"]))
            story.append(Spacer(1, 2))
            story.append(Paragraph("CONSULTA GERAL DO SISTEMA", estilos["subtitulo"]))
            story.append(Spacer(1, 8))
            
            # Linha decorativa central
            linha = Drawing(720, 4)
            linha.add(Line(150, 2, 570, 2, strokeColor=HexColorLib("#1a5276"), strokeWidth=2))
            story.append(linha)
            story.append(Spacer(1, 10))
            
            # ============================================================
            # ESTATÍSTICAS GERAIS
            # ============================================================
            estilo_secao_destaque = ParagraphStyle(
                "SecaoDestaque",
                parent=estilos["normal"],
                fontSize=12,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
                textColor=HexColorLib("#1a5276"),
                leading=16,
                spaceAfter=6,
            )
            
            story.append(Paragraph("═" * 50, estilos["normal"]))
            story.append(Paragraph("ESTATÍSTICAS GERAIS", estilo_secao_destaque))
            story.append(Paragraph("═" * 50, estilos["normal"]))
            story.append(Spacer(1, 6))
            
            # Tabela de estatísticas
            dados_estatisticas = [
                ["Métrica", "Valor"],
                ["Total de Eventos", str(total)],
                ["CRITICAL", str(critical)],
                ["WARNING", str(warning)],
                ["INFO", str(info)],
            ]
            
            tabela_estatisticas = Table(dados_estatisticas, colWidths=[4*cm, 4*cm])
            tabela_estatisticas.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColorLib("#1a5276")),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColorLib("#f0f4fa"), white]),
                ('GRID', (0, 0), (-1, -1), 0.5, HexColorLib("#b0c4d8")),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))
            
            story.append(tabela_estatisticas)
            story.append(Spacer(1, 12))
            
            # ============================================================
            # MÓDULOS ENCONTRADOS
            # ============================================================
            if modulos:
                story.append(Paragraph("═" * 50, estilos["normal"]))
                story.append(Paragraph("MÓDULOS ENCONTRADOS", estilo_secao_destaque))
                story.append(Paragraph("═" * 50, estilos["normal"]))
                story.append(Spacer(1, 4))
                
                dados_modulos = [["Módulo", "Eventos"]]
                for modulo, qtd in sorted(modulos.items(), key=lambda x: x[1], reverse=True):
                    dados_modulos.append([modulo, str(qtd)])
                
                # Limita a 10 módulos para não sobrecarregar
                if len(dados_modulos) > 11:
                    dados_modulos = dados_modulos[:11]
                    dados_modulos.append(["...", ""])
                
                tabela_modulos = Table(dados_modulos, colWidths=[5*cm, 4*cm])
                tabela_modulos.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColorLib("#2980b9")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColorLib("#f0f4fa"), white]),
                    ('GRID', (0, 0), (-1, -1), 0.5, HexColorLib("#b0c4d8")),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ]))
                
                story.append(tabela_modulos)
                story.append(Spacer(1, 12))
            
            # ============================================================
            # ÚLTIMOS 10 EVENTOS
            # ============================================================
            story.append(Paragraph("═" * 50, estilos["normal"]))
            story.append(Paragraph("ÚLTIMOS 10 EVENTOS", estilo_secao_destaque))
            story.append(Paragraph("═" * 50, estilos["normal"]))
            story.append(Spacer(1, 6))
            
            # Estilos para tabela de eventos
            estilo_celula = ParagraphStyle(
                "CelulaTexto",
                parent=estilos["normal"],
                fontSize=7,
                alignment=TA_LEFT,
                fontName="Helvetica",
                leading=9,
            )
            
            estilo_celula_center = ParagraphStyle(
                "CelulaCenter",
                parent=estilos["normal"],
                fontSize=7,
                alignment=TA_CENTER,
                fontName="Helvetica",
                leading=9,
            )
            
            estilo_cabecalho = ParagraphStyle(
                "CabecalhoTexto",
                parent=estilos["normal"],
                fontSize=8,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
                textColor=colors.whitesmoke,
                leading=10,
            )
            
            cabecalho_tabela_eventos = [
                Paragraph("Data/Hora", estilo_cabecalho),
                Paragraph("Tipo", estilo_cabecalho),
                Paragraph("Módulo", estilo_cabecalho),
                Paragraph("Descrição", estilo_cabecalho),
                Paragraph("Utilizador", estilo_cabecalho),
                Paragraph("Severidade", estilo_cabecalho),
            ]
            
            dados_tabela_eventos = [cabecalho_tabela_eventos]
            
            for evento in ultimos_eventos:
                if hasattr(evento, 'payload') and isinstance(evento.payload, dict):
                    payload = evento.payload
                    data_hora = evento.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    tipo = evento.event_type if hasattr(evento, 'event_type') else "EVENTO"
                    modulo = payload.get("modulo", "DESCONHECIDO")
                    descricao = payload.get("descricao", "")[:60]  # Limita tamanho
                    utilizador = payload.get("utilizador", "-") or "-"
                    severidade = payload.get("severidade", "INFO")
                    
                    # Quebra a descrição se for longa
                    if len(descricao) > 60:
                        descricao = descricao[:57] + "..."
                    
                    linha = [
                        Paragraph(data_hora, estilo_celula_center),
                        Paragraph(tipo, estilo_celula_center),
                        Paragraph(modulo, estilo_celula_center),
                        Paragraph(descricao, estilo_celula),
                        Paragraph(utilizador, estilo_celula_center),
                        Paragraph(severidade, estilo_celula_center),
                    ]
                    dados_tabela_eventos.append(linha)
            
            # Cria a tabela de eventos
            if len(dados_tabela_eventos) > 1:
                larguras = [2.2*cm, 1.5*cm, 2.0*cm, 4.0*cm, 2.0*cm, 1.8*cm]
                tabela_eventos = Table(dados_tabela_eventos, colWidths=larguras, repeatRows=1)
                
                estilo_tabela_eventos = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColorLib("#1a5276")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    ('TOPPADDING', (0, 0), (-1, 0), 6),
                    ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                    ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                    ('ALIGN', (2, 1), (2, -1), 'CENTER'),
                    ('ALIGN', (4, 1), (4, -1), 'CENTER'),
                    ('ALIGN', (5, 1), (5, -1), 'CENTER'),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColorLib("#f0f4fa"), white]),
                    ('GRID', (0, 0), (-1, -1), 0.5, HexColorLib("#b0c4d8")),
                    ('TOPPADDING', (0, 1), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ])
                
                # Cores por severidade
                cores_sev = {
                    "CRITICAL": HexColorLib("#cc3333"),
                    "WARNING": HexColorLib("#cc8800"),
                    "INFO": HexColorLib("#1a6c9a"),
                }
                
                for i in range(1, len(dados_tabela_eventos)):
                    if len(dados_tabela_eventos[i]) > 5:
                        # Pega a severidade da linha
                        sev_text = ultimos_eventos[i-1].payload.get("severidade", "INFO") if i-1 < len(ultimos_eventos) else "INFO"
                        if sev_text in cores_sev:
                            estilo_tabela_eventos.add('TEXTCOLOR', (5, i), (5, i), cores_sev[sev_text])
                            if sev_text == "CRITICAL":
                                estilo_tabela_eventos.add('BACKGROUND', (5, i), (5, i), HexColorLib("#ffebee"))
                            elif sev_text == "WARNING":
                                estilo_tabela_eventos.add('BACKGROUND', (5, i), (5, i), HexColorLib("#fff8e1"))
                
                tabela_eventos.setStyle(estilo_tabela_eventos)
                story.append(tabela_eventos)
            else:
                story.append(Paragraph("Nenhum evento encontrado.", estilos["normal"]))
            
            # ============================================================
            # RODAPE
            # ============================================================
            story.append(Spacer(1, 15))
            linha_inferior = Drawing(720, 4)
            linha_inferior.add(Line(0, 2, 720, 2, strokeColor=HexColorLib("#1a5276"), strokeWidth=1.5))
            story.append(linha_inferior)
            story.append(Spacer(1, 4))
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            story.append(Paragraph(
                "Relatório gerado automaticamente pelo Sistema Integrado de Segurança",
                estilos["rodape"]
            ))
            story.append(Paragraph(
                f"Documento: REL-{datetime.now().strftime('%Y%m%d')}-{timestamp[-4:]} | Versão: 1.0",
                estilos["rodape"]
            ))
            
            # ============================================================
            # CONSTRÓI O PDF
            # ============================================================
            print("[INFO] Construindo o PDF da Consulta Geral...")
            doc.build(story)
            
            print(f"[INFO] PDF da Consulta Geral gerado com sucesso: {caminho}")
            print("=" * 60 + "\n")
            
        except Exception as e:
            print(f"[ERRO] Falha ao gerar PDF da Consulta Geral: {e}")
            traceback.print_exc()
            print("[INFO] Usando fallback para estilo padrão")
            self._exportar_padrao(conteudo, titulo, caminho)


# ============================================================
# FUNÇÃO DE TESTE PARA VERIFICAR O MATPLOTLIB
# ============================================================

def testar_grafico_direto():
    """Teste direto para verificar se o matplotlib gera gráficos"""
    print("\n" + "=" * 60)
    print("[TESTE] Verificando geração de gráficos...")
    print("=" * 60)
    
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import tempfile
        import os
        
        # Cria um gráfico simples
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(['A', 'B', 'C'], [10, 20, 15])
        ax.set_title('Teste de Gráfico')
        ax.set_ylabel('Valores')
        
        # Salva em arquivo temporário
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            fig.savefig(tmp.name, format='png', dpi=100, bbox_inches='tight')
            tmp_path = tmp.name
        
        # Verifica se o arquivo foi criado
        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            print(f"[TESTE] ✅ Gráfico gerado com sucesso!")
            print(f"[TESTE] Arquivo: {tmp_path}")
            print(f"[TESTE] Tamanho: {os.path.getsize(tmp_path)} bytes")
            os.unlink(tmp_path)
            print(f"[TESTE] Arquivo temporário removido")
            return True
        else:
            print(f"[TESTE] ❌ Falha ao gerar gráfico")
            return False
            
    except Exception as e:
        print(f"[TESTE] ❌ ERRO: {e}")
        traceback.print_exc()
        return False


# ============================================================
# FUNÇÃO DE EXPORTAÇÃO SIMPLIFICADA
# ============================================================

def exportar_relatorio(conteudo, titulo, tipo="pdf", **kwargs):
    if tipo.lower() == "pdf":
        exportador = ExportadorPDF()
        return exportador.exportar(conteudo, titulo, **kwargs)
    elif tipo.lower() == "csv":
        exportador = ExportadorCSV()
        return exportador.exportar(conteudo, titulo, **kwargs)
    else:
        raise ValueError(f"Tipo de exportação inválido: {tipo}")


# ============================================================
# EXECUTA O TESTE SE FOR EXECUTADO DIRETAMENTE
# ============================================================

if __name__ == "__main__":
    testar_grafico_direto()