# 🔍 Verificar Instalación de Docker

## Problema Detectado

Docker no se encuentra en el PATH. Esto puede significar:
1. Docker está descargado pero no instalado
2. Docker está instalado pero no está en el PATH
3. Docker Desktop no está corriendo

## Soluciones por Sistema Operativo

### macOS

#### Opción 1: Docker Desktop (Recomendado)

1. **Descargar Docker Desktop**:
   - Ve a https://www.docker.com/products/docker-desktop/
   - Descarga Docker Desktop para Mac
   - Instala el archivo `.dmg`

2. **Abrir Docker Desktop**:
   - Busca "Docker" en Applications
   - Abre Docker Desktop
   - Espera a que se inicie (verás el ícono de Docker en la barra superior)

3. **Verificar instalación**:
   ```bash
   docker --version
   docker compose version
   ```

#### Opción 2: Homebrew

```bash
# Instalar Docker Desktop con Homebrew
brew install --cask docker

# O instalar solo docker-compose
brew install docker-compose
```

### Linux

#### Instalar Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Agregar usuario al grupo docker
sudo usermod -aG docker $USER

# Cerrar sesión y volver a entrar, luego verificar:
docker --version
```

#### Instalar Docker Compose

```bash
# Versión nueva (plugin)
sudo apt-get update
sudo apt-get install docker-compose-plugin

# O versión standalone
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Windows

1. **Descargar Docker Desktop**:
   - Ve a https://www.docker.com/products/docker-desktop/
   - Descarga Docker Desktop para Windows
   - Instala el ejecutable

2. **Abrir Docker Desktop**:
   - Busca "Docker Desktop" en el menú de inicio
   - Abre Docker Desktop
   - Espera a que se inicie

3. **Verificar en PowerShell o CMD**:
   ```powershell
   docker --version
   docker compose version
   ```

## Verificar que Docker Está Funcionando

Después de instalar, verifica:

```bash
# Verificar Docker
docker --version
# Debería mostrar: Docker version 24.x.x o similar

# Verificar Docker Compose
docker compose version
# O si tienes versión antigua:
docker-compose --version

# Verificar que Docker está corriendo
docker info
# Debería mostrar información del sistema Docker

# Probar con un contenedor simple
docker run hello-world
# Debería descargar y ejecutar un contenedor de prueba
```

## Si Docker Desktop Está Instalado pero No Funciona

### macOS

1. **Verificar que Docker Desktop está corriendo**:
   - Busca el ícono de Docker en la barra superior
   - Si no está, abre Docker Desktop desde Applications

2. **Reiniciar Docker Desktop**:
   - Click derecho en el ícono de Docker → Quit Docker Desktop
   - Abrir Docker Desktop nuevamente

3. **Verificar permisos**:
   - Docker Desktop → Settings → Resources
   - Asegúrate de que tiene recursos asignados

### Linux

```bash
# Verificar que el servicio está corriendo
sudo systemctl status docker

# Si no está corriendo, iniciarlo
sudo systemctl start docker
sudo systemctl enable docker  # Para iniciar automáticamente al arrancar
```

## Usar el Script Automático

Una vez que Docker esté funcionando, usa el script:

```bash
cd docker
./ejecutar.sh
```

El script detectará automáticamente tu versión de Docker Compose y ejecutará los comandos correctos.

## Próximos Pasos

1. ✅ Instalar Docker Desktop o Docker
2. ✅ Verificar que `docker --version` funciona
3. ✅ Verificar que `docker compose version` o `docker-compose --version` funciona
4. ✅ Ejecutar `cd docker && ./ejecutar.sh`
