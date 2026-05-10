"""
Teste de indexação ISOLADO - sem servidor.
Mostra qualquer erro com stack trace completo.

Uso:
  python scripts\\test_index.py https://github.com/tiangolo/fastapi
  python scripts\\test_index.py C:\\path\\to\\local\\repo
"""
import sys
import os
import traceback
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / "backend" / ".env")


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts\\test_index.py <url ou path>")
        sys.exit(1)

    repo_input = sys.argv[1]
    print(f"\n=== Teste de Indexação ===")
    print(f"Input: {repo_input}\n")

    from agents.indexer import index_repository

    def progress(stage, data):
        msg = data.get("message", str(data))
        print(f"  [{stage:15}] {msg}")

    try:
        result = index_repository(repo_input, on_progress=progress)
        print(f"\n=== SUCESSO ===")
        print(f"Files indexed: {result['files_indexed']}")
        print(f"Code files:    {result['code_files']}")
        print(f"Chunks:        {result['chunks']}")
        print(f"Symbols:       {result['graph_info']['symbols_count']}")
        print(f"\nProfile:")
        for k, v in result["profile"].items():
            v_str = str(v)
            if len(v_str) > 120:
                v_str = v_str[:120] + "..."
            print(f"  {k:25} {v_str}")
    except Exception as e:
        print(f"\n=== ERRO ===")
        print(f"Tipo: {type(e).__name__}")
        print(f"Msg:  {e}")
        print(f"\nStack trace completo:")
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
