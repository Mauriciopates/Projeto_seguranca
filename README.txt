RELATORIOS.PY v2.0.3- SISTEMA DE GERACAO DE RELATORIOS


Atualização da versão v2.0.3:
----------------------------

- Mudança para README.txt (Orientado pelo formador)
- Informação do caminho dos LOGS no README
- Informação da Versão na tela inicial do Sistema 
- Correção de algumas tipagens no código ui.py antes de gerar o executavel
- Criação do executavel na pasta Executavel/Executavel v2.0.3


ALTERAÇÃO DE VERSIONAMENTO
---------------------------

ui.py ->
__version__ = "V2.0.3"

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

   

COMANDOS PARA CRIAÇÃO DA PRÓXIMA VERSÃO DO EXECUTAVEL
-----------------------------------------------------

No terminal VScode rodar o código: mude os numeros da versão antes ->


Remove-Item -Recurse -Force build, "Executavel v2.0.x.spec" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "Executavel\Executavel v2.0.x" -ErrorAction SilentlyContinue

.venv\Scripts\pyinstaller.exe --noconfirm --onedir --windowed --distpath ".\Executavel" --workpath ".\build" --name "Executavel v2.0.x" --collect-data matplotlib --hidden-import matplotlib.backends.backend_tkagg --add-data "README.txt;." main.py

Copy-Item -Recurse -Force ".\logs" ".\Executavel\Executavel v2.0.x\logs"


**Antes de rodar, não esquece de atualizar a versão em dois lugares no código 
(senão o build funciona, mas o app continua se identificando como 2.0.3 por dentro):

ui.py → __version__ = "2.0.4"
README.txt → atualizar o changelog com o que mudou nessa versão


- Código faz a integração do Exe sem dependencia das pastas de log fora tudo integrado a pasta somente para enviar 
- Apagar sempre a pasta build para não gerar uma poluição de dados é uma pasta temporária usada durante a montagem do executável

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