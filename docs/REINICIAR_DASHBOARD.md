# 🔄 Cómo Reiniciar el Dashboard

Si el dashboard no está mostrando los cambios más recientes, sigue estos pasos:

## Opción 1: Usar el Script Automático (Recomendado)

```bash
./scripts/restart_dashboard.sh
```

Este script:
- ✅ Limpia la caché de Vite
- ✅ Detiene cualquier proceso en el puerto 5173
- ✅ Reinicia el servidor de desarrollo

## Opción 2: Reinicio Manual

### Paso 1: Detener el servidor actual

Si el dashboard está corriendo, presiona `Ctrl+C` en la terminal donde está corriendo.

O si no tienes acceso a esa terminal:

```bash
# En macOS/Linux
lsof -ti :5173 | xargs kill -9

# Verificar que el puerto esté libre
lsof -i :5173
```

### Paso 2: Limpiar caché

```bash
cd dashboard
rm -rf node_modules/.vite
rm -rf dist
```

### Paso 3: Reiniciar el servidor

```bash
npm run dev
```

## Opción 3: Limpiar Caché del Navegador

Si después de reiniciar el servidor aún ves la versión antigua:

1. **Chrome/Edge**: 
   - Presiona `Ctrl+Shift+R` (Windows/Linux) o `Cmd+Shift+R` (Mac)
   - O abre DevTools (F12) → Click derecho en el botón de recargar → "Vaciar caché y volver a cargar de forma forzada"

2. **Firefox**:
   - Presiona `Ctrl+F5` (Windows/Linux) o `Cmd+Shift+R` (Mac)

3. **Safari**:
   - Presiona `Cmd+Option+R`
   - O Safari → Preferencias → Avanzado → Activar "Mostrar menú Desarrollo" → Desarrollo → "Vaciar cachés"

## Verificar que Funciona

Después de reiniciar, deberías ver:

1. ✅ El dashboard carga en `http://localhost:5173`
2. ✅ Los clicks funcionan en todas las tarjetas
3. ✅ El botón "Saldo Bancario" abre el dashboard financiero
4. ✅ Los botones de aprobar/rechazar funcionan en las propuestas

## Problemas Comunes

### El puerto 5173 está ocupado

```bash
# Ver qué proceso está usando el puerto
lsof -i :5173

# Matar el proceso
kill -9 <PID>
```

### Los cambios no se reflejan

1. Verifica que guardaste los archivos
2. Revisa la consola del navegador (F12) por errores
3. Verifica que el servidor de desarrollo esté corriendo
4. Limpia la caché del navegador (ver Opción 3)

### Error: "Cannot find module"

```bash
cd dashboard
rm -rf node_modules
npm install
npm run dev
```

## Notas

- El servidor de desarrollo de Vite debería recargar automáticamente cuando cambias archivos
- Si no se recarga automáticamente, presiona `Ctrl+R` o `Cmd+R` en el navegador
- Los headers de no-cache están configurados para desarrollo, pero el navegador puede cachear recursos
