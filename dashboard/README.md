# ARIA Dashboard

Dashboard web para ARIA - Autonomous Resource Intelligence Agent.

## Requisitos

- Node.js 18+
- npm o pnpm

## Instalación

```bash
cd dashboard
npm install
```

## Desarrollo

```bash
# Inicia el servidor de desarrollo
npm run dev
```

El dashboard estará disponible en http://localhost:5173

## Producción

```bash
# Construye para producción
npm run build

# Previsualiza la build
npm run preview
```

## Configuración

El dashboard se conecta a la API de ARIA en `http://localhost:8000` por defecto.
Esto se configura en `vite.config.js` mediante el proxy.

Para conectar a otra URL, modifica el proxy en `vite.config.js`:

```javascript
server: {
  proxy: {
    '/api': {
      target: 'http://your-api-url:8000',
      changeOrigin: true,
    },
  },
},
```

## Características

- 📊 KPIs en tiempo real
- 🤖 Estado de todos los agentes
- ⚡ Propuestas pendientes con acciones rápidas
- 🔄 Actualización automática cada 30 segundos
- 🎨 Diseño moderno con Tailwind CSS
- 📱 Responsive para móvil y desktop
