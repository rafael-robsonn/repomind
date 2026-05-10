"""
Teste end-to-end completo do pipeline.
Roda: index → review com diff de exemplo → mostra resultado.

Uso:
  python scripts/test_e2e.py <repo_path> [diff_file]

Exemplo:
  python scripts/test_e2e.py C:\\projects\\meu-repo sample_diffs\\01_consistency.diff
"""
import sys
import os
from pathlib import Path

# Add backend to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / "backend" / ".env")


def banner(text, char="─", color="\033[36m"):
    line = char * 70
    print(f"\n{color}{line}\n  {text}\n{line}\033[0m")


def main():
    if not os.getenv("AMD_API_KEY") or os.getenv("AMD_API_KEY") == "your_amd_api_key_here":
        print("\033[31m✕ AMD_API_KEY não configurada\033[0m")
        print("Configure backend/.env com AMD_BASE_URL, AMD_API_KEY, AMD_MODEL")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Uso: python scripts/test_e2e.py <repo_path> [diff_file]")
        sys.exit(1)

    repo_path = sys.argv[1]
    diff_file = sys.argv[2] if len(sys.argv) > 2 else None

    if not Path(repo_path).exists():
        print(f"\033[31m✕ Repo não existe: {repo_path}\033[0m")
        sys.exit(1)

    from agents.indexer import index_repository
    from agents.pipeline import run_review_pipeline

    # ── 1. Index
    banner("INDEXANDO REPOSITÓRIO", "═", "\033[35m")

    def index_progress(stage, data):
        msg = data.get("message", "")
        print(f"  \033[33m[{stage:12}]\033[0m {msg}")

    result = index_repository(repo_path, on_progress=index_progress)

    print(f"\n\033[32m✓ Indexação completa\033[0m")
    print(f"  Files indexed:  {result['files_indexed']}")
    print(f"  Code files:     {result['code_files']}")
    print(f"  Chunks:         {result['chunks']}")
    print(f"  Symbols:        {result['graph_info']['symbols_count']}")
    print(f"  Imports:        {result['graph_info']['import_edges']}")

    print(f"\n\033[36mPROFILE:\033[0m")
    profile = result["profile"]
    print(f"  Purpose:      {profile.get('purpose', '?')[:120]}")
    print(f"  Architecture: {profile.get('architecture', '?')}")
    print(f"  Languages:    {profile.get('main_languages', [])}")
    print(f"  Frameworks:   {profile.get('frameworks', [])}")
    if profile.get("notable_patterns"):
        print(f"  Patterns:")
        for p in profile["notable_patterns"][:3]:
            print(f"    - {p}")

    # ── 2. Diff
    if diff_file and Path(diff_file).exists():
        diff = Path(diff_file).read_text()
        banner(f"USANDO DIFF: {diff_file}", "═", "\033[35m")
    else:
        diff = """diff --git a/src/example.py b/src/example.py
@@ -10,6 +10,12 @@ class UserService:
     def get_user(self, user_id: int) -> User:
         return self.db.query(User).filter(User.id == user_id).first()
 
+    def delete_user(self, uid):
+        u = self.db.query(User).filter(User.id == uid).first()
+        self.db.delete(u)
+        self.db.commit()
+        return True
+
"""
        banner("USANDO DIFF DE EXEMPLO", "═", "\033[35m")

    print(diff)

    # ── 3. Review
    banner("EXECUTANDO PIPELINE DE REVIEW", "═", "\033[35m")

    def pipeline_progress(stage, data):
        elapsed = data.get("elapsed", "")
        elapsed_str = f" ({elapsed}s)" if elapsed else ""
        print(f"  \033[33m[{stage:25}]\033[0m{elapsed_str}")
        if "context_files" in data:
            print(f"      → {len(data['context_files'])} context files")
        if "queries" in data:
            for q in data["queries"][:3]:
                print(f"      → query: \"{q[:60]}\"")
        if "raw_issues_count" in data:
            print(f"      → {data['raw_issues_count']} issues raised")
        if "validated" in data:
            print(f"      → {data['validated']} kept, {data['rejected']} filtered")

    review = run_review_pipeline(
        diff=diff,
        collection_name=result["collection"],
        project_profile=result["profile"],
        emitter=pipeline_progress,
    )

    if "error" in review:
        print(f"\n\033[31m✕ Erro: {review['error']}\033[0m")
        sys.exit(1)

    # ── 4. Resultado
    banner("RESULTADO", "═", "\033[35m")
    report = review["report"]

    color = "\033[32m" if report["approved"] else "\033[31m"
    icon = "✓" if report["approved"] else "✕"
    print(f"{color}{icon} {'APROVADO' if report['approved'] else 'MUDANÇAS NECESSÁRIAS'}\033[0m")
    print(f"\n{report['overall_verdict']}\n")

    print(f"\033[36mEstatísticas:\033[0m")
    for k, v in report["stats"].items():
        print(f"  {k:25} {v}")

    if report["issues"]:
        print(f"\n\033[36mIssues validados:\033[0m\n")
        for i, iss in enumerate(report["issues"], 1):
            sev_color = {
                "critical": "\033[31m", "major": "\033[33m",
                "minor": "\033[93m", "suggestion": "\033[32m"
            }.get(iss["severity"], "")
            print(f"  {sev_color}[{i}] {iss['severity'].upper():10}\033[0m {iss['file']}")
            print(f"      \033[1m{iss['description']}\033[0m")
            print(f"      Why: {iss['justification'][:200]}")
            print(f"      Fix: \033[32m{iss['suggestion'][:200]}\033[0m\n")

    if report.get("rejected_issues"):
        print(f"\033[35mFiltrados pelo Critic ({len(report['rejected_issues'])}):\033[0m")
        for iss in report["rejected_issues"][:3]:
            print(f"  ✕ {iss['description'][:100]}")
            print(f"    razão: {iss.get('_rejection_reason', '?')[:120]}\n")

    print(f"\n\033[36mTimings:\033[0m")
    for stage, t in review["timings"].items():
        print(f"  {stage:20} {t:.2f}s")
    total = sum(review["timings"].values())
    print(f"  {'TOTAL':20} \033[1m{total:.2f}s\033[0m")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\033[33mInterrompido\033[0m")
    except Exception as e:
        import traceback
        print(f"\n\033[31m✕ Erro: {type(e).__name__}: {e}\033[0m")
        traceback.print_exc()
        sys.exit(1)
