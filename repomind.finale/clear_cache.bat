@echo off
REM Limpa caches que precisam ser rebuilds depois de updates do grafo/embeddings
REM Repos clonados são preservados (cloned_repos\)
echo.
echo Limpando caches do RepoMind...
echo.

if exist chroma_db (
    rmdir /s /q chroma_db
    echo [OK] chroma_db removido
)

if exist .repomind_cache (
    rmdir /s /q .repomind_cache
    echo [OK] .repomind_cache removido
)

echo.
echo Cache limpo. Reinicie o backend e reindexe seus repos.
echo (cloned_repos preservado, clones nao precisam refazer download)
echo.
