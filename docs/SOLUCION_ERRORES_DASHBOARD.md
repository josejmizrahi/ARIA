# 🔧 Solución de Errores del Dashboard

## ❌ Errores Comunes y Soluciones

### Error: `Cannot find module 'tailwindcss-animate'`

**Causa:** Las dependencias no están instaladas en tu máquina local.

**Solución:**
```bash
cd /Users/jj/ARIA/dashboard
npm install
```

### Error: `Cannot find module '@radix-ui/react-*'`

**Causa:** Los paquetes de Radix UI no están instalados.

**Solución:**
```bash
cd /Users/jj/ARIA/dashboard
npm install @radix-ui/react-separator @radix-ui/react-select @radix-ui/react-label @radix-ui/react-avatar @radix-ui/react-slot @radix-ui/react-tabs
```

O simplemente:
```bash
cd /Users/jj/ARIA/dashboard
npm install
```

### Error: `require is not defined` en tailwind.config.js

**Causa:** El archivo `tailwind.config.js` está usando sintaxis CommonJS (`require`) pero el proyecto usa ES modules.

**Solución:**
El archivo debe tener al inicio:
```javascript
import tailwindcssAnimate from "tailwindcss-animate"
```

Y al final:
```javascript
plugins: [tailwindcssAnimate],
```

**NO usar:**
```javascript
plugins: [require("tailwindcss-animate")],
```

## 🚀 Solución Completa Paso a Paso

### 1. Actualizar el código desde Git

```bash
cd /Users/jj/ARIA
git pull origin cursor/planificaci-n-financiera-agente-cd71
```

### 2. Instalar todas las dependencias

```bash
cd dashboard
npm install
```

O usar el script automático:
```bash
cd dashboard
./install-deps.sh
```

### 3. Verificar que las dependencias estén instaladas

```bash
npm list tailwindcss-animate @radix-ui/react-separator @radix-ui/react-select
```

Deberías ver algo como:
```
aria-dashboard@0.1.0
├── @radix-ui/react-select@2.2.6
├── @radix-ui/react-separator@1.1.8
└── tailwindcss-animate@1.0.7
```

### 4. Limpiar caché si es necesario

```bash
rm -rf node_modules/.vite
rm -rf dist
```

### 5. Reiniciar el servidor

```bash
npm run dev
```

## ✅ Verificación Final

Si todo está correcto, deberías ver:

```
VITE v5.4.21  ready in XXX ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

**Sin errores** sobre módulos faltantes.

## 📋 Lista de Dependencias Requeridas

Asegúrate de que tu `package.json` incluya:

```json
{
  "dependencies": {
    "@radix-ui/react-avatar": "^1.1.11",
    "@radix-ui/react-label": "^2.1.8",
    "@radix-ui/react-select": "^2.2.6",
    "@radix-ui/react-separator": "^1.1.8",
    "@radix-ui/react-slot": "^1.2.4",
    "@radix-ui/react-tabs": "^1.1.13",
    "tailwindcss-animate": "^1.0.7",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "tailwind-merge": "^3.4.0"
  }
}
```

## 🐛 Si los Errores Persisten

1. **Eliminar node_modules y reinstalar:**
   ```bash
   rm -rf node_modules package-lock.json
   npm install
   ```

2. **Verificar versión de Node.js:**
   ```bash
   node --version
   ```
   Debe ser Node.js 18+ o superior.

3. **Verificar que el archivo tailwind.config.js esté correcto:**
   ```bash
   head -1 dashboard/tailwind.config.js
   ```
   Debe mostrar: `import tailwindcssAnimate from "tailwindcss-animate"`

4. **Verificar que no haya conflictos de caché:**
   ```bash
   rm -rf node_modules/.vite
   rm -rf .vite
   ```

## 📞 Comandos de Diagnóstico

```bash
# Verificar dependencias instaladas
npm list --depth=0

# Verificar versión de Node
node --version

# Verificar versión de npm
npm --version

# Limpiar todo y reinstalar
rm -rf node_modules package-lock.json
npm install

# Probar build
npm run build
```
