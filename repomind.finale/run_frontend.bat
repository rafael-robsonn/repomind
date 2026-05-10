@echo off
cd frontend
if not exist node_modules (
    echo Instalando dependencias do frontend...
    npm install
)
npm run dev
