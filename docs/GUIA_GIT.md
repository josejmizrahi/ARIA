# 📝 Guía de Git para ARIA

## 🔧 Comandos Básicos de Git

### Ver Estado Actual

```bash
# Ver qué archivos han cambiado
git status

# Ver diferencias específicas
git diff

# Ver diferencias de un archivo específico
git diff aria/agents/finance_agent.py
```

### Agregar Cambios

```bash
# Agregar un archivo específico
git add aria/agents/finance_agent.py

# Agregar todos los archivos modificados
git add .

# Agregar todos los cambios (incluyendo eliminados)
git add -A

# Agregar solo archivos modificados (no nuevos)
git add -u
```

### Hacer Commit

```bash
# Commit simple
git commit -m "Descripción del cambio"

# Commit con descripción más detallada
git commit -m "feat: Agregar nueva funcionalidad

- Detalle 1
- Detalle 2
- Detalle 3"

# Commit de múltiples líneas (abre editor)
git commit
```

### Ver Historial

```bash
# Ver últimos commits
git log

# Ver últimos 10 commits
git log -10

# Ver commits de forma compacta
git log --oneline

# Ver commits con gráfico
git log --graph --oneline --all
```

### Push (Subir Cambios)

```bash
# Push a la rama actual
git push

# Push a rama específica (primera vez)
git push -u origin nombre-rama

# Push forzado (¡CUIDADO! Solo si es necesario)
git push --force
```

### Pull (Bajar Cambios)

```bash
# Bajar cambios del remoto
git pull

# Bajar cambios de rama específica
git pull origin nombre-rama
```

## 🎯 Flujo de Trabajo Recomendado

### 1. Verificar Estado

```bash
git status
```

### 2. Agregar Cambios

```bash
# Opción 1: Agregar archivos específicos
git add archivo1.py archivo2.py

# Opción 2: Agregar todos los cambios
git add -A
```

### 3. Hacer Commit

```bash
git commit -m "feat: Descripción del cambio"
```

### 4. Push

```bash
git push
```

## 📋 Convenciones de Mensajes de Commit

### Formato Recomendado

```
tipo(scope): descripción corta

Descripción detallada (opcional)

- Cambio 1
- Cambio 2
```

### Tipos de Commit

- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `docs`: Cambios en documentación
- `style`: Cambios de formato (no afectan código)
- `refactor`: Refactorización de código
- `test`: Agregar o modificar tests
- `chore`: Tareas de mantenimiento

### Ejemplos

```bash
# Nueva funcionalidad
git commit -m "feat(finanzas): Agregar análisis de ratios financieros"

# Corrección
git commit -m "fix(dashboard): Arreglar clicks en tarjetas"

# Documentación
git commit -m "docs: Agregar guía de uso del sistema"

# Múltiples cambios
git commit -m "feat(finanzas): Sistema de presupuestos flexible

- Carga desde Odoo Budget Module
- Configuración manual desde dashboard
- Cálculo automático desde histórico
- Endpoints API para gestión"
```

## 🔄 Trabajar con Ramas

### Ver Ramas

```bash
# Ver ramas locales
git branch

# Ver todas las ramas (locales y remotas)
git branch -a
```

### Crear Nueva Rama

```bash
# Crear y cambiar a nueva rama
git checkout -b nueva-rama

# O con git switch (más moderno)
git switch -c nueva-rama
```

### Cambiar de Rama

```bash
# Cambiar a rama existente
git checkout nombre-rama

# O con git switch
git switch nombre-rama
```

### Merge (Fusionar)

```bash
# Cambiar a rama principal
git checkout main

# Fusionar otra rama
git merge nombre-rama
```

## ⚠️ Comandos Útiles pero Peligrosos

### Deshacer Cambios

```bash
# Descartar cambios en archivo (¡CUIDADO! Se pierden cambios)
git checkout -- archivo.py

# Deshacer último commit (mantiene cambios)
git reset --soft HEAD~1

# Deshacer último commit (elimina cambios)
git reset --hard HEAD~1
```

### Ver Cambios Antes de Commit

```bash
# Ver qué se agregó al staging
git diff --staged

# Ver cambios de un commit específico
git show abc123
```

## 🎯 Ejemplo Completo

```bash
# 1. Ver qué cambió
git status

# 2. Ver diferencias
git diff

# 3. Agregar cambios
git add -A

# 4. Verificar qué se va a commitear
git status

# 5. Hacer commit
git commit -m "feat(finanzas): Agregar análisis de ratios

- Validación automática de campos
- Cálculo de margen neto
- Análisis de tendencias históricas"

# 6. Push
git push

# O si es primera vez en la rama
git push -u origin nombre-rama
```

## 📚 Recursos Adicionales

- [Git Documentation](https://git-scm.com/doc)
- [GitHub Guides](https://guides.github.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)
