# 🎨 Dashboard con shadcn/ui - Guía Visual

## ✨ Nuevo Dashboard Completamente Rehecho

El dashboard ha sido completamente reescrito usando **solo componentes de shadcn/ui**, eliminando todos los componentes personalizados.

## 🚀 Cómo Acceder

1. **Iniciar el Dashboard:**
   ```bash
   cd dashboard
   npm run dev
   ```

2. **Abrir en el navegador:**
   ```
   http://localhost:5173
   ```

3. **Asegurarse de que la API esté corriendo:**
   ```bash
   aria api
   # O
   python -m aria.api.app
   ```

## 🎯 Componentes Principales

### Dashboard Principal (`App.jsx`)

**Características:**
- ✅ Header con logo y controles usando `Card` y `Button`
- ✅ Selector de empresa usando `Select` de shadcn/ui
- ✅ KPIs usando `KPICard` (basado en `Card`)
- ✅ Tarjetas de agentes usando `AgentCard` (basado en `Card`)
- ✅ Propuestas usando `ProposalCard` (basado en `Card`)
- ✅ Botones usando `Button` con variantes (outline, ghost, etc.)

**Componentes shadcn/ui utilizados:**
- `Button` - Todos los botones
- `Card` - Todas las tarjetas
- `Select` - Selector de empresa
- `Badge` - Indicadores de estado
- `Separator` - Separadores visuales

### Dashboard Financiero (`FinanceDashboard.jsx`)

**Características:**
- ✅ Sistema de tabs usando `Tabs` de shadcn/ui
- ✅ Métricas financieras usando `MetricCard`
- ✅ Gráficos usando `SimpleBarChart`
- ✅ Configuración de presupuestos usando `Input` y `Label`
- ✅ Comparativos usando `Card` y `Badge`

**Tabs disponibles:**
1. **Resumen** - Vista general con saldos y métricas clave
2. **Ratios** - Ratios financieros y tendencias
3. **Presupuesto** - Comparativo vs presupuesto
4. **Rentabilidad** - Análisis de rentabilidad y márgenes
5. **Proyecciones** - Escenarios optimista, realista y pesimista

**Componentes shadcn/ui utilizados:**
- `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent`
- `Card` - Todas las tarjetas
- `Input` - Campos de entrada
- `Label` - Etiquetas
- `Button` - Botones de acción
- `Badge` - Indicadores de variación
- `Separator` - Separadores

### Conversaciones (`AgentConversations.jsx`)

**Características:**
- ✅ Sistema de tabs para conversaciones y mensajes
- ✅ Burbujas de mensaje usando `Card`
- ✅ Filtro usando `Input`
- ✅ Badges de prioridad usando `Badge`

**Componentes shadcn/ui utilizados:**
- `Tabs` - Navegación entre conversaciones y mensajes
- `Card` - Burbujas de mensaje
- `Input` - Campo de búsqueda
- `Badge` - Indicadores de prioridad
- `Button` - Botones de acción

## 🧩 Componentes Reutilizables Creados

### `KPICard`
Tarjeta de indicador clave con:
- Título y valor
- Subtítulo opcional
- Icono opcional
- Estado (ok, warning, critical)
- Tendencia opcional

### `AgentCard`
Tarjeta de agente con:
- Nombre del agente
- Icono
- Badge de estado
- Métricas específicas del agente

### `ProposalCard`
Tarjeta de propuesta con:
- Título y descripción
- Badges de agente y prioridad
- Botones de aprobar/rechazar

### `MetricCard`
Tarjeta de métrica financiera con:
- Título y valor
- Subtítulo
- Icono
- Estado visual
- Tendencia opcional

### `SimpleBarChart`
Gráfico de barras simple con:
- Título
- Datos dinámicos
- Barras proporcionales
- Valores formateados

## 🎨 Sistema de Diseño

### Colores (shadcn/ui)
- Modo oscuro por defecto
- Variables CSS para temas
- Colores semánticos (primary, secondary, destructive, etc.)

### Tipografía
- Fuentes del sistema
- Jerarquía clara con `CardTitle`, `CardDescription`
- Texto monoespaciado para números

### Espaciado
- Sistema de espaciado consistente
- Grid responsivo
- Padding y margins uniformes

## 🔧 Configuración

### Archivos de Configuración

**`components.json`** - Configuración de shadcn/ui
```json
{
  "style": "default",
  "rsc": false,
  "tsx": false,
  "tailwind": {
    "config": "tailwind.config.js",
    "css": "src/index.css",
    "baseColor": "slate",
    "cssVariables": true
  }
}
```

**`tailwind.config.js`** - Configuración de Tailwind con tema de shadcn/ui

**`vite.config.js`** - Configuración de Vite con alias `@/`

## 📦 Dependencias Instaladas

```json
{
  "@radix-ui/react-avatar": "^1.0.4",
  "@radix-ui/react-label": "^2.0.2",
  "@radix-ui/react-select": "^2.0.0",
  "@radix-ui/react-separator": "^1.0.3",
  "@radix-ui/react-slot": "^1.0.2",
  "@radix-ui/react-tabs": "^1.0.4",
  "class-variance-authority": "^0.7.1",
  "clsx": "^2.1.1",
  "tailwind-merge": "^3.4.0",
  "tailwindcss-animate": "^1.0.7"
}
```

## 🎯 Ventajas del Nuevo Dashboard

1. **Consistencia**: Todos los componentes siguen el mismo patrón de diseño
2. **Reutilización**: Componentes completamente reutilizables
3. **Accesibilidad**: Basado en Radix UI (accesible por defecto)
4. **Mantenibilidad**: Código más limpio y fácil de mantener
5. **Escalabilidad**: Fácil agregar nuevos componentes siguiendo el patrón
6. **Documentación**: shadcn/ui tiene excelente documentación

## 🐛 Solución de Problemas

### El dashboard no carga
1. Verificar que el servidor esté corriendo: `npm run dev`
2. Verificar que no haya errores en la consola del navegador
3. Limpiar caché: `rm -rf node_modules/.vite`

### Los clicks no funcionan
1. Verificar que estés usando la versión más reciente
2. Recargar la página con `Ctrl+Shift+R` (o `Cmd+Shift+R` en Mac)
3. Verificar la consola del navegador por errores

### Los datos no se cargan
1. Verificar que la API esté corriendo en `http://localhost:8000`
2. Verificar la consola del navegador por errores de red
3. Verificar que el proxy esté configurado en `vite.config.js`

## 📸 Capturas de Pantalla

El nuevo dashboard incluye:

- **Vista principal**: Grid de KPIs y agentes
- **Dashboard financiero**: Tabs con múltiples vistas
- **Conversaciones**: Sistema de mensajes entre agentes
- **Modo oscuro**: Tema oscuro por defecto

## 🚀 Próximos Pasos

1. Probar todas las funcionalidades
2. Verificar que los clicks funcionen correctamente
3. Revisar la responsividad en diferentes tamaños de pantalla
4. Agregar más componentes de shadcn/ui según sea necesario
