"""
main.py - Ponto de entrada da aplicação
"""
import sys
import os
from pathlib import Path

# Adiciona o diretório atual ao path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui import InterfaceRelatorios


def main():
    """Função principal"""
    try:
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