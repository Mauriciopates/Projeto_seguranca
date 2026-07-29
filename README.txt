RELATORIOS.PY v2.0.2- SISTEMA DE GERACAO DE RELATORIOS


Atualização da versão v2.0.2:

- Criação do README.txt 
- Informação do caminho dos LOGS no README
- Informação da Versão na tela inicial do Sistema


CAMINHO DOS LOGS:

core.py ->

DIRETORIO_BASE = Path(__file__).resolve().parent

PASTA_LOGS = DIRETORIO_BASE / "logs"
PASTA_RELATORIOS = DIRETORIO_BASE / "relatorios_exportacao"

PASTA_LOGS.mkdir(parents=True, exist_ok=True)
PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)



1. DEPENDÊNCIAS NECESSÁRIAS
---------------------------

Versão necessária Python: 3.11

Para utilizar todas as funcionalidades (PDF e gráficos), instale as dependências num ambiente virtual.

--- OPÇÃO A: Usando 'uv' (Caso tenha o 'uv' instalado) ---

*Criar e instalar dependências:
   uv venv
   .\.venv\Scripts\activate   # (no Linux/macOS use: source .venv/bin/activate)
   uv pip install reportlab matplotlib

**Lembrar de selecionar o ambiente virutal uv --> caminho criado de acordo com a maquina na versão do python

--- OPÇÃO B: Usando o caminho do Python instalado e ambiente virtual (.venv) ---

Caso não instale com a uv descrita e não encontrando o python, selecionar após criação do .venv

python -m pip install reportlab matplotlib

ou

py -m pip install reportlab matplotlib 

--- OPÇÃO C: Usando Python Padrão (Recomendado) ---

1. Criar o ambiente virtual:
   python -m venv .venv

2. Ativar o ambiente virtual:
   - Windows (PowerShell): .\.venv\Scripts\Activate.ps1
   - Windows (CMD):        .\.venv\Scripts\activate.bat
   - Linux / macOS:        source .venv/bin/activate

3. Instalar as bibliotecas:
   pip install reportlab matplotlib


----------------------Organização do projeto------------------------------ 

Projeto_seguranca/
│
├── core.py          ← Este arquivo completo (coração do sistema)
├── exportacao.py    ← Exportação PDF/CSV
├── ui.py            ← Interface gráfica 
├── main.py          ← Ponto de entrada
│
├── logs/            ← Pasta com os arquivos .log
└── relatorios_exportacao/  ← Pasta onde os PDF/CSV serão salvos



- Elisama : core.py e exportacao.py (BACK) (CLasse Pai / Mãe)


core.py - O que você faz:
Define o que é um Evento (cada linha de log)

Gerencia o EstadoDoSistema (todos os eventos juntos)

Lê os arquivos de log com ler_logs_pasta()

Extrai usuários dos logs com extrair_utilizadores()

Conta estatísticas com extrair_estatisticas()


exportacao.py - O que você faz: ->  (Herda/Importa)
Cria a classe base ExportadorBase (molde)

Implementa ExportadorCSV (gera planilhas)

Implementa ExportadorPDF (gera relatórios)

Oferece a função exportar_relatorio() (fácil de usar)



- Mauricio:  ui.py  (FRONT) (Importa e usa)

O que a colega faz na ui.py:
Cria a janela com botões

Mostra os relatórios na tela

Chama as funções do seu core.py

Usa seu exportacao.py para salvar arquivos