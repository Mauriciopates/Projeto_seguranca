RELATORIOS.PY v2.1.1 - SISTEMA DE GERACAO DE RELATORIOS
 

 Nova atualização v2.1.1
 -----------------------

 - Mudamos pasta caminho do Log
   auditoria.py passou a gravar dentro da MESMA pasta "Logs" que os
   demais modulos usam (C:\260462\Logs), no arquivo "relatorios.log" -
   nao existe mais a pasta separada "Auditoria"
 - Mudamos jeito que esta gerando os logs com as regras repassadas para os demais com severidade
 » AAAA-MM-DD HH:MM:SS [SEVERIDADE] MODULO NOME_DO_MODULO: descricao do evento 

 »» atualização maior anterior para rastreamento. »»
- Instalação automática da pasta Logs no executável
  main.py copia a pasta "Logs" empacotada para C:\260462\Logs na
  primeira execução, se o destino ainda estiver sem logs de módulo.
  O relatorios.log (auditoria) não conta nessa verificação.
- Comando do executável voltou a ter --add-data "logs;Logs"
 
ATUALIZACAO DA VERSAO v2.1.0
-----------------------------
 
[Interface (ui.py)]
- Detalhamento por Modulo reformulado: pop-up de selecao do modulo +
  tabela dos eventos so daquele modulo
- Tela inicial reorganizada: botoes separados em "RELATORIOS" e
  "FERRAMENTAS E ACOES", com icones

 
[Novo arquivo: auditoria.py]
- Log de auditoria proprio da aplicação, separado dos logs que o sistema
  analisa - regista quem exportou o que e quando releu os logs
- Independente do core.py, a pasta so e criada quando alguma acao
  realmente acontece
 
[core.py - regras de leitura de logs]
- Severidade somente aceitar [CRITICO] , [AVISO] e [INFO]
- Palavra "MODULO" agora e exigida SEM acento
- Caminho base dos logs alterado para pasta fixa C:\260462 (deixou de
  ser relativo a posicao do main.py/executavel)
 
[Executavel]
- Comando de build atualizado com --collect-data matplotlib e
  --hidden-import matplotlib.backends.backend_tkagg (necessario para os
  graficos do Analitico funcionarem dentro do executavel)
 
 
>>> AVISO DE COMPATIBILIDADE <<<
Logs ja existentes que usam CRITICAL/WARNING (ingles) ou MODULO com
acento deixam de ser lidos corretamente a partir desta versao (o evento
continua a aparecer, mas como severidade INFO e/ou modulo
DESCONHECIDO). E necessario avisar TODAS as equipas de modulo sobre o
novo formato antes de atualizar para esta versao em producao.

Regras de versão

tipos de alteração...
├── Quebrou o sistema antigo ou mudou totalmente a arquitetura? ──> Sobe MAJOR (v3.0.0)
├── Adicionou um recurso/funcionalidade nova que funciona? ──────> Sobe MINOR (v2.1.0)
└── Corrigiu um erro/bug ou fez um pequeno ajuste visual? ───────> Sobe PATCH (v2.0.3)


ALTERAÇÃO DE VERSIONAMENTO
---------------------------

ui.py ->
__version__ = "2.1.1"


CAMINHO LEITURA DOS LOGS:
-----------------

core.py ->
 
DIRETORIO_BASE = Path(r"C:\260462")
 
PASTA_LOGS = DIRETORIO_BASE / "Logs"
PASTA_RELATORIOS = DIRETORIO_BASE / "relatorios_exportacao"
 
PASTA_LOGS.mkdir(parents=True, exist_ok=True)
PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)
 
auditoria.py ->
 
PASTA_AUDITORIA = DIRETORIO_BASE / "Logs"   (MESMA pasta "Logs" acima, nao uma pasta separada)
FICHEIRO_AUDITORIA = PASTA_AUDITORIA / "relatorios.log"

«« Para ler os logs é necessário fazer a cópia da pasta log aqui dentro para o caminho acima.


FORMATO OBRIGATORIO DE LOG (para as equipas de modulo)
----------------------------------------------------------
 
Uma linha por evento, exatamente assim:
 
AAAA-MM-DD HH:MM:SS [SEVERIDADE] MODULO NOME_DO_MODULO: descricao do evento
 
- Data/hora: AAAA-MM-DD HH:MM:SS (sem milissegundos, sem virgula)
- Severidade: CRITICO, AVISO ou INFO (qualquer outra palavra vira INFO
  automaticamente, incluindo termos em ingles)
- "MODULO": palavra literal, MAIUSCULA, SEM acento
- Nome do modulo: uma palavra, maiuscula (ex: CAMARAS, ALARMES,
  AUTENTICACAO, SENSORES, ACESSOS, RECONHECIMENTO, BACKUPS, RELATORIOS,
  UTILIZADORES)
- Para associar a acao a um utilizador, escrever exatamente:
  utilizador 'nome_aqui'
- Arquivo com extensao .log ou .txt, codificacao UTF-8, dentro da pasta
  Logs
 
Exemplo certo:
2026-07-31 09:45:12 [CRITICO] MODULO ALARMES: Alarme AL-003 alterado de
DESACTIVADO para ACTIVO. Motivo: Intrusao detetada


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

 
Antes de rodar, atualizar a versao em dois lugares (senao o build
funciona, mas o app continua se identificando com o numero antigo por
dentro):

- ui.py -> __version__ = "X.X.X"
- README.txt -> atualizar o changelog com o que mudou nessa versao
 
No terminal do VSCode, com a .venv (Python 3.11) ativada, trocar
"X.X.X" pelo numero real da versao em TODOS os lugares abaixo:

>>

 
Remove-Item -Recurse -Force build, "Relatorios_interface v2.X.X.spec" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "Executavel\Relatorios_interface v2.X.X" -ErrorAction SilentlyContinue

.venv\Scripts\pyinstaller.exe --noconfirm --onedir --windowed --distpath ".\Executavel" --workpath ".\build" --name "Relatorios_interface v2.X.X" --collect-data matplotlib --hidden-import matplotlib.backends.backend_tkagg --add-data "logs;Logs" --add-data "README.txt;." main.py



<<
 
>>> MUDOU NA VERSAO 2.1.0 <<<
Nao copiar mais a pasta "logs" pra dentro do executavel (o antigo passo
"Copy-Item ... logs" das versoes anteriores nao se aplica mais). Como o
caminho agora e fixo (C:\260462 - ver secao "CAMINHO BASE E LEITURA DOS
LOGS" acima), o app sempre le e escreve em C:\260462\Logs (inclusive o
auditoria.py, que grava o relatorios.log na mesma pasta) e
C:\260462\relatorios_exportacao, nao importa onde o .exe esteja
instalado.
 
Isso muda a forma de distribuir o executavel: como as pastas de dados
nao viajam mais dentro do .zip do executavel, o computador que for
rodar o app precisa ter a pasta C:\260462\Logs com os arquivos de log
la dentro (o app cria as pastas sozinho na primeira execucao, mas
comecam vazias - sem log nenhum pra analisar).
 
Depois de gerar, apagar a pasta "build" - e so material temporario
usado durante a montagem do executavel, nao faz parte do app, e pode
virar poluicao de dados se acumular entre varias versoes (ela e
recriada do zero automaticamente no proximo build).




----------------------Organização do projeto------------------------------ 

Projeto_seguranca/
│
├── core.py          ← Este arquivo completo (coração do sistema)
├── exportacao.py    ← Exportação PDF/CSV
├── ui.py            ← Interface gráfica 
├──auditoria.py      ← gera logs
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



- Mauricio:  ui.py e auditoria.py  (FRONT) (Importa e usa)

ui.py: Cria a janela com botões

Mostra os relatórios na tela

Chama as funções do seu core.py

Usa seu exportacao.py para salvar arquivos

auditoria.py :  Criação dos logs de rastreamento