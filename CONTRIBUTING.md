# Contributing to RepoMind

Thanks for your interest in contributing! 🎉

## Reporting bugs

Use the [Issues](https://github.com/<SEU_USER>/repomind/issues) tab and follow the bug report template. Include:

- Python and Node versions
- OS
- Steps to reproduce
- Expected vs. observed behavior
- Relevant logs (no secrets!)

## Suggesting features

Open an issue with the `enhancement` label describing:

- The problem the feature solves
- How you imagine the solution
- Alternatives considered

## Development workflow

1. **Fork** the repo
2. **Clone** your fork: `git clone https://github.com/<your-user>/repomind.git`
3. **Create a branch**: `git checkout -b feat/feature-name` or `fix/bug-name`
4. **Develop** following the project's code style
5. **Test** locally: `python scripts/test_e2e.py`
6. **Commit** with descriptive messages (see convention below)
7. **Push** and open a **Pull Request** with a clear description

## Commit convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <short description>

[optional body]

[optional footer]
```

**Common types:**

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` refactor with no functional change
- `test:` tests
- `chore:` maintenance (deps, build, CI)
- `perf:` performance improvement

**Examples:**

```
feat(reviewer): add dynamic few-shot support
fix(indexer): fix off-by-one in Python class chunking
docs(readme): update architecture diagram
```

## Code style

### Python
- Formatter: **black** (line-length 100)
- Linter: **ruff**
- Type hints where it makes sense
- Docstrings on public functions (Google style)

```bash
cd backend
black . && ruff check .
```

### JavaScript/JSX
- Formatter: **prettier**
- Linter: **eslint**

```bash
cd frontend
npm run lint && npm run format
```

## Tests

Keep coverage on new code. Run before opening a PR:

```bash
# backend
cd backend && pytest

# E2E
python scripts/test_e2e.py
```

## Pull Requests

- Keep PRs small and focused (1 feature/fix per PR)
- Link the related issue (`Closes #123`)
- Describe the **what** and the **why**, not just the how
- Wait for CI to pass before requesting a review
- Be open to feedback — reviews are collaborative

## Code of Conduct

Be respectful, constructive, and patient. Technical disagreements are welcome; personal attacks are not.

---

Questions? Open an [issue](https://github.com/<SEU_USER>/repomind/issues) with the `question` label.
