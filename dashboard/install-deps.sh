#!/bin/bash
# Script para instalar todas las dependencias necesarias del dashboard

echo "🔧 Instalando dependencias del dashboard ARIA..."

cd "$(dirname "$0")" || exit 1

echo "📦 Instalando dependencias de npm..."
npm install

echo "✅ Verificando dependencias críticas..."
npm list tailwindcss-animate @radix-ui/react-separator @radix-ui/react-select @radix-ui/react-label @radix-ui/react-avatar @radix-ui/react-slot @radix-ui/react-tabs 2>&1 | grep -E "(aria-dashboard|├──|└──)" || echo "⚠️  Algunas dependencias pueden faltar"

echo ""
echo "✅ Instalación completada!"
echo ""
echo "🚀 Para iniciar el dashboard:"
echo "   npm run dev"
echo ""
