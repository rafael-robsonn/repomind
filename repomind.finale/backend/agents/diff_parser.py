"""
Structured diff parsing - extracts files, hunks, added/removed lines, affected symbols.
"""
from dataclasses import dataclass, field
from typing import Optional
import re

try:
    from unidiff import PatchSet
    HAS_UNIDIFF = True
except ImportError:
    HAS_UNIDIFF = False


@dataclass
class DiffHunk:
    file: str
    old_start: int
    new_start: int
    added_lines: list[tuple[int, str]] = field(default_factory=list)  # (line_num, content)
    removed_lines: list[tuple[int, str]] = field(default_factory=list)
    context: str = ""  # raw hunk text


@dataclass
class ParsedDiff:
    files: list[str] = field(default_factory=list)
    hunks: list[DiffHunk] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    raw: str = ""

    def files_changed(self) -> list[str]:
        return list(dict.fromkeys(self.files))

    def to_summary(self) -> str:
        lines = [f"Arquivos modificados: {len(set(self.files))}"]
        lines.append(f"Linhas adicionadas: {self.additions}")
        lines.append(f"Linhas removidas: {self.deletions}")
        for f in set(self.files):
            file_hunks = [h for h in self.hunks if h.file == f]
            adds = sum(len(h.added_lines) for h in file_hunks)
            dels = sum(len(h.removed_lines) for h in file_hunks)
            lines.append(f"  - {f}: +{adds}/-{dels}")
        return "\n".join(lines)


def parse_diff(diff_text: str) -> ParsedDiff:
    parsed = ParsedDiff(raw=diff_text)

    if HAS_UNIDIFF:
        try:
            patch = PatchSet(diff_text)
            for pf in patch:
                filename = pf.target_file or pf.source_file
                if filename.startswith(("a/", "b/")):
                    filename = filename[2:]
                parsed.files.append(filename)

                for hunk in pf:
                    h = DiffHunk(
                        file=filename,
                        old_start=hunk.source_start,
                        new_start=hunk.target_start,
                    )
                    for line in hunk:
                        if line.is_added:
                            h.added_lines.append((line.target_line_no, line.value.rstrip("\n")))
                            parsed.additions += 1
                        elif line.is_removed:
                            h.removed_lines.append((line.source_line_no, line.value.rstrip("\n")))
                            parsed.deletions += 1
                    h.context = str(hunk)
                    parsed.hunks.append(h)
            return parsed
        except Exception:
            pass

    return _parse_diff_regex(diff_text)


def _parse_diff_regex(diff_text: str) -> ParsedDiff:
    parsed = ParsedDiff(raw=diff_text)
    current_file = None
    current_hunk = None

    for line in diff_text.split("\n"):
        if line.startswith("+++"):
            m = re.match(r"\+\+\+ (?:b/)?(.+)", line)
            if m:
                current_file = m.group(1).strip()
                if current_file != "/dev/null":
                    parsed.files.append(current_file)
        elif line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if m and current_file:
                current_hunk = DiffHunk(
                    file=current_file,
                    old_start=int(m.group(1)),
                    new_start=int(m.group(2)),
                )
                parsed.hunks.append(current_hunk)
        elif current_hunk:
            if line.startswith("+") and not line.startswith("+++"):
                current_hunk.added_lines.append((current_hunk.new_start, line[1:]))
                parsed.additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_hunk.removed_lines.append((current_hunk.old_start, line[1:]))
                parsed.deletions += 1

    return parsed


def affected_symbols(parsed: ParsedDiff) -> list[dict]:
    """Heurística: identifica símbolos (funções/classes) afetados."""
    affected = []
    for hunk in parsed.hunks:
        for _, content in hunk.added_lines + hunk.removed_lines:
            if m := re.match(r"^\s*(?:async\s+)?def\s+(\w+)", content):
                affected.append({"file": hunk.file, "symbol": m.group(1), "kind": "function"})
            elif m := re.match(r"^\s*class\s+(\w+)", content):
                affected.append({"file": hunk.file, "symbol": m.group(1), "kind": "class"})
            elif m := re.match(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)", content):
                affected.append({"file": hunk.file, "symbol": m.group(1), "kind": "function"})
    return affected
