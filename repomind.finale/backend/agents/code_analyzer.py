"""
AST-level code analysis using tree-sitter.
Extracts symbols, imports, and dependencies from source files.

Suporta dois backends:
- tree_sitter_language_pack (novo, Python 3.12+)
- tree_sitter_languages (antigo, Python 3.8-3.11)
"""
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
import re

_get_parser = None

try:
    from tree_sitter_language_pack import get_parser as _get_parser
    HAS_TREE_SITTER = True
except ImportError:
    try:
        from tree_sitter_languages import get_parser as _get_parser
        HAS_TREE_SITTER = True
    except ImportError:
        pass


LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".rb": "ruby",
}


@dataclass
class Symbol:
    name: str
    kind: str  # function | class | method | variable
    line: int
    end_line: int
    parent: Optional[str] = None
    docstring: Optional[str] = None
    signature: Optional[str] = None


@dataclass
class FileAnalysis:
    path: str
    language: str
    loc: int  # lines of code
    imports: list[str] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["symbols"] = [asdict(s) for s in self.symbols]
        return d


def _walk_tree(node, source_bytes: bytes, lang: str, parent: Optional[str] = None):
    """Recursive walker - returns list of Symbol objects."""
    symbols = []
    imports = []

    if lang == "python":
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
                params_node = node.child_by_field_name("parameters")
                signature = ""
                if params_node:
                    signature = source_bytes[params_node.start_byte:params_node.end_byte].decode("utf-8", errors="ignore")
                docstring = _extract_python_docstring(node, source_bytes)
                symbols.append(Symbol(
                    name=name,
                    kind="method" if parent else "function",
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent=parent,
                    docstring=docstring,
                    signature=f"{name}{signature}",
                ))

        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
                docstring = _extract_python_docstring(node, source_bytes)
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent=parent,
                    docstring=docstring,
                ))
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        sub_syms, sub_imps = _walk_tree(child, source_bytes, lang, parent=name)
                        symbols.extend(sub_syms)
                        imports.extend(sub_imps)
                return symbols, imports

        elif node.type in ("import_statement", "import_from_statement"):
            text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
            imports.append(text.strip())

    elif lang in ("javascript", "typescript"):
        if node.type in ("function_declaration", "method_definition", "arrow_function"):
            name_node = node.child_by_field_name("name")
            if name_node:
                name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
                kind = "method" if node.type == "method_definition" else "function"
                symbols.append(Symbol(
                    name=name,
                    kind=kind,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent=parent,
                ))

        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent=parent,
                ))
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        sub_syms, sub_imps = _walk_tree(child, source_bytes, lang, parent=name)
                        symbols.extend(sub_syms)
                        imports.extend(sub_imps)
                return symbols, imports

        elif node.type == "import_statement":
            text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
            imports.append(text.strip())

    for child in node.children:
        sub_syms, sub_imps = _walk_tree(child, source_bytes, lang, parent)
        symbols.extend(sub_syms)
        imports.extend(sub_imps)

    return symbols, imports


def _extract_python_docstring(node, source_bytes: bytes) -> Optional[str]:
    body = node.child_by_field_name("body")
    if not body or not body.children:
        return None
    first = body.children[0]
    if first.type == "expression_statement" and first.children:
        expr = first.children[0]
        if expr.type == "string":
            text = source_bytes[expr.start_byte:expr.end_byte].decode("utf-8", errors="ignore")
            return text.strip("\"'").strip()[:300]
    return None


def _fallback_regex_analysis(content: str, ext: str) -> tuple[list[Symbol], list[str]]:
    """Fallback when tree-sitter is unavailable."""
    symbols = []
    imports = []
    lines = content.split("\n")

    if ext == ".py":
        for i, line in enumerate(lines, 1):
            if m := re.match(r"^\s*def\s+(\w+)\s*\(", line):
                symbols.append(Symbol(name=m.group(1), kind="function", line=i, end_line=i))
            elif m := re.match(r"^\s*class\s+(\w+)", line):
                symbols.append(Symbol(name=m.group(1), kind="class", line=i, end_line=i))
            elif re.match(r"^(import|from)\s+", line):
                imports.append(line.strip())

    elif ext in (".js", ".jsx", ".ts", ".tsx"):
        for i, line in enumerate(lines, 1):
            if m := re.match(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)", line):
                symbols.append(Symbol(name=m.group(1), kind="function", line=i, end_line=i))
            elif m := re.match(r"^\s*(?:export\s+)?class\s+(\w+)", line):
                symbols.append(Symbol(name=m.group(1), kind="class", line=i, end_line=i))
            elif m := re.match(r"^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(", line):
                symbols.append(Symbol(name=m.group(1), kind="function", line=i, end_line=i))
            elif re.match(r"^\s*import\s+", line):
                imports.append(line.strip())

    return symbols, imports


def analyze_file(filepath: Path, content: str) -> FileAnalysis:
    """Analyze a source file and extract structural info."""
    ext = filepath.suffix
    lang = LANG_MAP.get(ext, "unknown")
    loc = len([l for l in content.split("\n") if l.strip()])

    analysis = FileAnalysis(
        path=str(filepath),
        language=lang,
        loc=loc,
    )

    if lang == "unknown":
        return analysis

    symbols = []
    imports = []

    if HAS_TREE_SITTER and lang in ("python", "javascript", "typescript", "go", "rust", "java"):
        try:
            parser = _get_parser(lang)
            tree = parser.parse(content.encode("utf-8"))
            symbols, imports = _walk_tree(tree.root_node, content.encode("utf-8"), lang)
        except Exception:
            symbols, imports = _fallback_regex_analysis(content, ext)
    else:
        symbols, imports = _fallback_regex_analysis(content, ext)

    analysis.symbols = symbols
    analysis.imports = imports
    return analysis


def detect_project_type(file_paths: list[Path]) -> dict:
    """Heurística para identificar tipo de projeto."""
    files = [p.name for p in file_paths]
    indicators = {
        "python": any(f in files for f in ["pyproject.toml", "setup.py", "requirements.txt"]),
        "node": "package.json" in files,
        "rust": "Cargo.toml" in files,
        "go": "go.mod" in files,
        "java_maven": "pom.xml" in files,
        "java_gradle": any(f in files for f in ["build.gradle", "build.gradle.kts"]),
        "docker": "Dockerfile" in files,
        "k8s": any(f.endswith(".yaml") or f.endswith(".yml") for f in files),
    }

    frameworks = []
    if indicators["node"]:
        for p in file_paths:
            if p.name == "package.json":
                try:
                    text = p.read_text(encoding="utf-8")
                    if "react" in text: frameworks.append("react")
                    if "next" in text: frameworks.append("nextjs")
                    if "vue" in text: frameworks.append("vue")
                    if "express" in text: frameworks.append("express")
                    if "fastify" in text: frameworks.append("fastify")
                except: pass

    if indicators["python"]:
        for p in file_paths:
            if p.name == "requirements.txt":
                try:
                    text = p.read_text(encoding="utf-8").lower()
                    if "django" in text: frameworks.append("django")
                    if "flask" in text: frameworks.append("flask")
                    if "fastapi" in text: frameworks.append("fastapi")
                except: pass

    return {
        "stack": [k for k, v in indicators.items() if v],
        "frameworks": frameworks,
    }
