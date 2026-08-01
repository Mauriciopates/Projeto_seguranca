"""
main.py - Ponto de entrada da aplicação
"""

import sys
import os
import shutil
from pathlib import Path

# Adiciona o diretório atual ao path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui import InterfaceRelatorios

# Caminho fixo onde o sistema le os logs (mesmo do core.py)
DESTINO_LOGS = Path(r"C:\260462\Logs")


def garantir_logs_iniciais():
    """Copia a pasta Logs empacotada no executavel para C:\\260462\\Logs,
    mas SO se o destino ainda nao existir ou estiver vazio.

    Assim, ao enviar o executavel para outra pessoa, a pasta de logs de
    exemplo e instalada automaticamente no caminho certo na primeira
    execucao. Se a pessoa nao quiser usar, e so apagar - nas proximas
    execucoes nada e copiado por cima (o teste "esta vazio?" impede
    sobrescrever logs reais que ja estejam la).

    IMPORTANTE: para isto funcionar no executavel, o build precisa
    incluir a pasta no pacote:
        --add-data "logs;Logs"
    Sem esse parametro, nao existe pasta de origem dentro do executavel
    e nada e copiado (falha silenciosa).
    """
    try:
        # Identifica a origem da pasta Logs
        if getattr(sys, "frozen", False):
            # Executável compilado pelo PyInstaller
            base_path = Path(sys._MEIPASS)  # type: ignore
        else:
            # Execução via código-fonte
            base_path = Path(__file__).resolve().parent

        # Aceita "Logs" ou "logs" como nome da pasta de origem
        origem_logs = base_path / "Logs"
        if not origem_logs.exists():
            origem_logs = base_path / "logs"

        if not origem_logs.exists():
            print(
                f"[Logs] Nenhuma pasta de logs empacotada encontrada em: {base_path}\n"
                f"       (se for o executavel, confirme o parametro "
                f'--add-data "logs;Logs" no comando do PyInstaller)'
            )
            return

        # Verifica se o destino ja tem logs "de verdade".
        # ATENCAO: o proprio auditoria.py grava o "relatorios.log" nesta
        # mesma pasta assim que o sistema roda - por isso ele NAO conta
        # como conteudo aqui. Se contasse, bastava abrir o app uma vez
        # para a pasta nunca mais ser considerada vazia, e os logs de
        # exemplo nunca seriam instalados.
        if DESTINO_LOGS.exists():
            logs_existentes = [
                p
                for p in DESTINO_LOGS.iterdir()
                if p.is_file() and p.name.lower() != "relatorios.log"
            ]
        else:
            logs_existentes = []

        destino_vazio = len(logs_existentes) == 0
        if destino_vazio:
            DESTINO_LOGS.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(origem_logs, DESTINO_LOGS, dirs_exist_ok=True)
            total = len(list(DESTINO_LOGS.glob("*")))
            print(f"[Logs] {total} arquivo(s) copiado(s) para {DESTINO_LOGS}")
        else:
            print(f"[Logs] {DESTINO_LOGS} ja tem conteudo - nada foi copiado")

    except Exception as e:
        print(f"Aviso ao inicializar pasta de logs: {e}")


def main():
    """Função principal"""
    try:
        # Garante os logs no caminho C:\260462\Logs antes de iniciar a interface
        garantir_logs_iniciais()

        app = InterfaceRelatorios()
        app.executar()
    except KeyboardInterrupt:
        print("\nAplicação interrompida pelo usuário.")
    except Exception as e:
        print(f"Erro inesperado: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
