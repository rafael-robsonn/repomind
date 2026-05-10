# 🛠️ Build do RepoMind.exe

Guia pra gerar um único `RepoMind.exe` com tudo dentro.

---

## ⚠️ Antes de buildar — leia isso

**O EXE não inclui:**
- **Ollama** — tem que estar instalado separadamente (https://ollama.com)
- **Modelo de 9GB** — tem que rodar `ollama pull qwen2.5-coder:14b` antes
- **Node.js / Python** — só precisam pra BUILDAR, não pra rodar o EXE

**O EXE inclui:**
- Backend FastAPI completo
- Frontend React buildado (servido pelo próprio backend)
- Todas as deps Python (chromadb, langchain, sentence-transformers, etc)

**Tamanho esperado:** ~400-700MB

---

## 📋 Pré-requisitos pra buildar

1. Setup completo já rodado (`setup.bat`)
2. Backend funcionando (`run_backend.bat` deve abrir sem erro)
3. Node.js 18+ pro build do frontend
4. ~3GB de espaço livre em disco (build temporário)

---

## 🚀 Build em 1 comando

Na pasta do projeto:

```cmd
build.bat
```

Isso faz:
1. **Build do frontend** (`npm run build` → `frontend/dist`)
2. **Instala PyInstaller** no venv (se faltar)
3. **Empacota tudo** em `dist/RepoMind.exe`

Demora **5 a 10 minutos** dependendo da máquina.

---

## 🧪 Testando o EXE

```cmd
dist\RepoMind.exe
```

Vai:
1. Abrir um terminal preto com o banner ASCII
2. Verificar se Ollama tá rodando
3. Iniciar o servidor em http://localhost:8000
4. Abrir o navegador automaticamente

**Pasta de dados:** o EXE cria `chroma_db/`, `.repomind_cache/` e `backend/.env` **ao lado de onde você rodar**. Então mantenha o EXE numa pasta dedicada.

---

## 📦 Distribuindo o EXE

Pra mandar pra outras pessoas:
- Zip a pasta `dist/`
- Inclua **um README curto** dizendo:
  - Instalar Ollama
  - Rodar `ollama pull qwen2.5-coder:14b`
  - Dar dois cliques em `RepoMind.exe`

---

## 🐛 Problemas comuns

### Build falha em "ImportError: cannot import name X"

Adicione o módulo em `RepoMind.spec` no array `hiddenimports`. Faz rebuild.

### Antivírus bloqueia o EXE

Normal com PyInstaller. Soluções:
- Windows Defender → "Mais informações" → "Executar mesmo assim"
- Pra distribuir publicamente: assine digitalmente o EXE (custa $)

### EXE abre e fecha imediatamente

Roda pelo CMD pra ver o erro:

```cmd
cd dist
RepoMind.exe
```

A mensagem fica visível e o terminal espera Enter antes de fechar.

### "Failed to execute script launcher"

Geralmente import faltando. Roda em modo debug pra ver o stack trace:

```cmd
pyinstaller RepoMind.spec --clean --noconfirm --debug=imports
```

### EXE muito grande

Removeu coisa em `excludes` no `.spec`. Ou habilita compressão UPX (já tá habilitada). Não dá pra ficar muito menor que 400MB com torch + chromadb.

### Ollama não detectado

O EXE checa Ollama no startup. Se errar:
- Abre o app do Ollama (ícone na bandeja)
- Ou roda `ollama serve` num terminal separado

---

## 🔧 Customização

### Adicionar ícone

1. Coloca `icon.ico` na raiz do projeto
2. No `RepoMind.spec`, descomenta a linha `# icon="icon.ico"`
3. Rebuild

### Esconder console (modo windowed)

No `RepoMind.spec`, muda `console=True` pra `console=False`. **Não recomendo** — você perde a visibilidade dos logs e fica difícil debugar.

### Build mais rápido (modo onedir)

Em vez de `--onefile`, gera uma pasta com EXE + libs ao lado. Inicia mais rápido (não precisa descomprimir). Pra fazer isso:

No `.spec`, troca o bloco `EXE(...)` por:

```python
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="RepoMind", ...)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name="RepoMind")
```

Resulta em `dist/RepoMind/RepoMind.exe` + libs.

---

## ✅ Checklist final antes de distribuir

- [ ] Ollama instalado e modelo baixado
- [ ] `dist/RepoMind.exe` abre sem erro
- [ ] Navegador abre em localhost:8000 automaticamente
- [ ] UI carrega (não fica branco)
- [ ] Indexa um repo de teste com sucesso
- [ ] Pipeline de review funciona end-to-end
- [ ] Grafo 3D renderiza
