# 🆘 Ayuda Rápida - Solución de Problemas Comunes

## 🔄 Problema: No puedo hacer git pull

### Error: "Your local changes would be overwritten"

**Solución:**
```bash
# Guardar cambios locales
git stash

# Hacer pull
git pull origin cursor/planificaci-n-financiera-agente-cd71

# Recuperar cambios locales (si los necesitas)
git stash pop
```

### Error: "Branch diverged"

**Solución:**
```bash
# Ver diferencias
git fetch origin
git log HEAD..origin/cursor/planificaci-n-financiera-agente-cd71

# Hacer pull forzado (cuidado: sobrescribe cambios locales)
git reset --hard origin/cursor/planificaci-n-financiera-agente-cd71
```

### Error: "Permission denied" o "Authentication failed"

**Solución:**
```bash
# Verificar que tienes acceso
git remote -v

# Si necesitas autenticarte
git config --global user.name "Tu Nombre"
git config --global user.email "tu@email.com"
```

## 🚀 Problema: No puedo iniciar la API

### Error: "Module not found"

**Solución:**
```bash
# Instalar dependencias
pip install -r requirements.txt

# O con venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Error: "Port already in use"

**Solución:**
```bash
# Ver qué proceso usa el puerto
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Detener proceso
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# O usar el script
./scripts/kill_port_8000.sh
```

### Error: "Cannot connect to Odoo"

**Solución:**
```bash
# Verificar configuración
aria check

# Verificar que .env esté configurado
cat .env | grep ODOO
```

## 🎨 Problema: No puedo iniciar el Dashboard

### Error: "Cannot find module"

**Solución:**
```bash
cd dashboard
npm install
```

### Error: "tailwindcss-animate not found"

**Solución:**
```bash
cd dashboard
npm install tailwindcss-animate
```

### Error: "require is not defined" en tailwind.config.js

**Solución:**
Verificar que `tailwind.config.js` tenga:
```javascript
import tailwindcssAnimate from "tailwindcss-animate"
// ...
plugins: [tailwindcssAnimate],
```

NO debe tener:
```javascript
plugins: [require("tailwindcss-animate")],
```

## ☁️ Problema: No puedo ejecutar en la nube

### Error: "Connection refused"

**Solución:**
1. Verificar que el servidor escuche en `0.0.0.0`:
   ```bash
   aria api --host 0.0.0.0 --port 8000
   ```

2. Verificar firewall:
   ```bash
   sudo ufw allow 8000/tcp
   sudo ufw allow 5173/tcp
   ```

3. Verificar que el proceso esté corriendo:
   ```bash
   ps aux | grep aria
   ```

### Error: Dashboard no se conecta a API

**Solución:**
1. Configurar variable de entorno:
   ```bash
   export VITE_API_URL=http://TU_IP:8000
   cd dashboard
   npm run dev -- --host 0.0.0.0
   ```

2. O modificar `vite.config.js`:
   ```javascript
   proxy: {
     '/api': {
       target: 'http://TU_IP:8000',  // Cambiar aquí
       changeOrigin: true,
     },
   }
   ```

## 📋 Comandos de Diagnóstico

```bash
# Verificar estado de git
git status
git log --oneline -5

# Verificar configuración
aria check

# Verificar dependencias Python
pip list | grep aria

# Verificar dependencias Node
cd dashboard && npm list --depth=0

# Ver logs
tail -f logs/aria.log

# Verificar puertos
lsof -i :8000
lsof -i :5173
```

## 🔧 Reset Completo (Último Recurso)

Si nada funciona, reset completo:

```bash
# 1. Guardar cambios importantes
git stash

# 2. Resetear a la última versión del remoto
git fetch origin
git reset --hard origin/cursor/planificaci-n-financiera-agente-cd71

# 3. Limpiar dependencias Python
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Limpiar dependencias Node
cd dashboard
rm -rf node_modules package-lock.json
npm install

# 5. Limpiar caché
rm -rf node_modules/.vite
rm -rf dist
```

## 📞 ¿Qué información necesito para ayudarte?

Si sigues teniendo problemas, comparte:

1. **El comando exacto que ejecutaste**
2. **El error completo** (copia y pega)
3. **Tu sistema operativo** (macOS, Linux, Windows)
4. **Versión de Node/Python**:
   ```bash
   node --version
   python --version
   ```

## 🎯 Pasos Rápidos para Empezar de Cero

```bash
# 1. Clonar/Actualizar
git pull origin cursor/planificaci-n-financiera-agente-cd71

# 2. Instalar dependencias Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Instalar dependencias Dashboard
cd dashboard
npm install
cd ..

# 4. Configurar .env
cp env.example .env
# Editar .env con tus credenciales

# 5. Verificar
aria check

# 6. Iniciar
./scripts/start-cloud.sh
```
