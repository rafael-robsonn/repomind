"""
GitHub repo cloner - clona repos públicos pro filesystem local pra indexar.
Streams output em vez de buffer pra evitar travamento no Windows.
"""
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable


def is_github_url(text: str) -> bool:
    """Detecta se é URL de repo GitHub."""
    text = text.strip()
    return bool(re.match(r"https?://(www\.)?github\.com/[\w\-]+/[\w\-\.]+", text))


def is_local_path(text: str) -> bool:
    """Detecta se parece um caminho local válido."""
    text = text.strip()
    p = Path(text)
    return p.exists() and p.is_dir()


def parse_github_url(url: str) -> tuple[str, str]:
    """Extrai (owner, repo) de uma URL do GitHub."""
    m = re.match(r"https?://(?:www\.)?github\.com/([\w\-]+)/([\w\-\.]+?)(?:\.git)?(?:/.*)?$", url.strip())
    if not m:
        raise ValueError(f"URL GitHub inválida: {url}")
    return m.group(1), m.group(2)


def get_clone_dir() -> Path:
    """Diretório base onde clones ficam. Sempre fora de backend/ pra evitar reload."""
    # Default: <projeto>/cloned_repos (NÃO dentro de backend/)
    default = Path(__file__).parent.parent.parent / "cloned_repos"
    base = Path(os.getenv("REPOMIND_CLONES_DIR", str(default)))
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def _check_git_installed():
    """Verifica que git tá instalado no PATH."""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git --version falhou: {result.stderr}")
    except FileNotFoundError:
        raise RuntimeError(
            "Git não encontrado no PATH. Instale: https://git-scm.com/download/win"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("git --version travou. Algo errado com a instalação do Git.")


def _run_git_streaming(args: list, cwd: Optional[str] = None,
                       on_progress: Optional[Callable] = None,
                       timeout: int = 300) -> int:
    """
    Executa git com:
    - Variáveis de ambiente que DESABILITAM prompt de credenciais
    - Stream do stderr em tempo real (git progress vai pra stderr)
    - Timeout absoluto
    """
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    env["SSH_ASKPASS"] = "echo"
    env["GIT_PROGRESS_DELAY"] = "0"
    cmd = ["git"] + args

    if on_progress:
        on_progress(f"$ {' '.join(cmd)}")

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=1,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    output_lines = []

    def reader(stream, label):
        try:
            for line in iter(stream.readline, ""):
                if not line:
                    break
                line = line.rstrip()
                if line:
                    output_lines.append(f"[{label}] {line}")
                    if on_progress:
                        on_progress(line)
        except Exception:
            pass

    t_out = threading.Thread(target=reader, args=(proc.stdout, "out"), daemon=True)
    t_err = threading.Thread(target=reader, args=(proc.stderr, "err"), daemon=True)
    t_out.start()
    t_err.start()

    try:
        rc = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        raise RuntimeError(f"git timeout após {timeout}s")

    t_out.join(timeout=2)
    t_err.join(timeout=2)

    if rc != 0:
        last_lines = "\n".join(output_lines[-10:])
        raise RuntimeError(f"git falhou (rc={rc}):\n{last_lines}")

    return rc


def clone_github_repo(url: str, on_progress: Optional[Callable] = None) -> str:
    """
    Clona um repo do GitHub. Retorna o caminho local.
    Se já existe, reusa (NÃO faz pull pra ser mais rápido).
    """
    _check_git_installed()

    owner, repo = parse_github_url(url)
    clone_base = get_clone_dir()
    target = clone_base / f"{owner}__{repo}"

    if target.exists():
        if on_progress:
            on_progress(f"Repo já clonado em {target}, reutilizando")
        return str(target.resolve())

    if on_progress:
        on_progress(f"Clonando {owner}/{repo} em {target}...")

    try:
        _run_git_streaming(
            [
                "clone",
                "--depth", "1",
                "--single-branch",
                "--no-tags",
                "--progress",
                url,
                str(target),
            ],
            on_progress=on_progress,
            timeout=300,
        )
    except Exception as e:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        raise RuntimeError(f"Falha ao clonar {url}: {e}")

    if not target.exists():
        raise RuntimeError(f"Clone parecia OK mas {target} não existe")

    if on_progress:
        on_progress(f"Clone completo: {target}")

    return str(target.resolve())


def resolve_repo_input(input_str: str, on_progress: Optional[Callable] = None) -> str:
    """
    Aceita URL do GitHub OU caminho local. Retorna caminho local absoluto.
    """
    input_str = input_str.strip().strip('"').strip("'")

    if is_github_url(input_str):
        return clone_github_repo(input_str, on_progress=on_progress)

    p = Path(input_str)
    if not p.exists():
        raise FileNotFoundError(
            f"Caminho não existe: {input_str}\n"
            f"Forneça um caminho local válido ou uma URL do GitHub."
        )
    if not p.is_dir():
        raise NotADirectoryError(f"Não é um diretório: {input_str}")

    return str(p.resolve())
