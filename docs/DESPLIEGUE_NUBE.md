# ☁️ Guía de Despliegue en la Nube

Esta guía te ayudará a ejecutar ARIA completamente en la nube, sin necesidad de ejecutarlo localmente.

## 📋 Opciones de Despliegue

### Opción 1: Servidor Cloud (VPS/EC2/DigitalOcean)

#### Requisitos del Servidor

- **OS**: Ubuntu 22.04 LTS o superior (recomendado)
- **RAM**: Mínimo 2GB (4GB recomendado)
- **CPU**: 2 cores mínimo
- **Disco**: 20GB mínimo
- **Puertos**: 8000 (API), 5173 (Dashboard), 6379 (Redis - opcional)

#### Paso 1: Preparar el Servidor

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias básicas
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm git

# Instalar Docker y Docker Compose (opcional pero recomendado)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
sudo apt install -y docker-compose-plugin
```

#### Paso 2: Clonar el Repositorio

```bash
git clone https://github.com/josejmizrahi/ARIA.git
cd ARIA
```

#### Paso 3: Configurar Variables de Entorno

```bash
cp env.example .env
nano .env  # Editar con tus credenciales
```

**Configuración importante para producción:**

```env
# Entorno
ARIA_ENV=production
ARIA_DEBUG=false
ARIA_LOG_LEVEL=INFO

# Odoo
ODOO_URL=https://tu-instancia.odoo.com
ODOO_DB=tu_base_datos
ODOO_USER=tu_usuario
ODOO_PASSWORD=tu_contraseña
ODOO_COMPANY_ID=1

# Redis (si usas Docker Compose, usar redis://redis:6379/0)
REDIS_URL=redis://localhost:6379/0

# API URL (URL pública de tu servidor)
API_URL=http://TU_IP_O_DOMINIO:8000
```

#### Paso 4: Configurar Firewall

```bash
# Permitir puertos necesarios
sudo ufw allow 8000/tcp  # API
sudo ufw allow 5173/tcp  # Dashboard
sudo ufw enable
```

#### Paso 5: Ejecutar con Docker Compose (Recomendado)

```bash
cd docker
docker-compose -f docker-compose.prod.yml up -d
```

#### Paso 6: Ejecutar Sin Docker (Alternativa)

**Terminal 1 - API:**
```bash
cd /ruta/a/ARIA
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
aria api --host 0.0.0.0 --port 8000
```

**Terminal 2 - Dashboard:**
```bash
cd /ruta/a/ARIA/dashboard
npm install
npm run dev -- --host 0.0.0.0
```

**Terminal 3 - Redis (si no usas Docker):**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### Opción 2: Usar un Servicio de Hosting (Railway, Render, Fly.io)

#### Railway

1. **Crear cuenta en Railway**: https://railway.app
2. **Conectar repositorio de GitHub**
3. **Configurar servicios:**

   **Servicio 1 - API:**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `aria api --host 0.0.0.0 --port $PORT`
   - Variables de entorno: Configurar todas las del `.env`

   **Servicio 2 - Dashboard:**
   - Build Command: `cd dashboard && npm install && npm run build`
   - Start Command: `cd dashboard && npm run preview -- --host 0.0.0.0 --port $PORT`
   - Variables de entorno:
     - `VITE_API_URL`: URL del servicio API

#### Render

1. **Crear cuenta en Render**: https://render.com
2. **Crear Web Service para API:**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `aria api --host 0.0.0.0 --port $PORT`
   - Environment Variables: Configurar todas las del `.env`

3. **Crear Static Site para Dashboard:**
   - Build Command: `cd dashboard && npm install && npm run build`
   - Publish Directory: `dashboard/dist`
   - Environment Variables:
     - `VITE_API_URL`: URL del servicio API

### Opción 3: Usar un Servicio de Contenedores (Google Cloud Run, AWS ECS)

#### Google Cloud Run

```bash
# Construir imagen
gcloud builds submit --tag gcr.io/TU_PROYECTO/aria-api

# Desplegar
gcloud run deploy aria-api \
  --image gcr.io/TU_PROYECTO/aria-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000 \
  --set-env-vars "ODOO_URL=...,ODOO_DB=..."
```

## 🔧 Configuración del Dashboard para API Remota

### Opción A: Usar Variable de Entorno

En el servidor donde corre el dashboard, configurar:

```bash
export VITE_API_URL=http://TU_IP_O_DOMINIO:8000
cd dashboard
npm run dev -- --host 0.0.0.0
```

### Opción B: Modificar vite.config.js

```javascript
proxy: {
  '/api': {
    target: 'http://TU_IP_O_DOMINIO:8000',  // Cambiar aquí
    changeOrigin: true,
  },
}
```

### Opción C: Build de Producción

```bash
cd dashboard
npm run build
# Servir dist/ con nginx o cualquier servidor web
```

## 🔒 Seguridad en Producción

### 1. Usar HTTPS (Recomendado)

**Con Nginx como reverse proxy:**

```nginx
server {
    listen 80;
    server_name tu-dominio.com;
    
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location / {
        proxy_pass http://localhost:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Con Certbot para SSL:**

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d tu-dominio.com
```

### 2. Restringir CORS (Opcional)

En `aria/api/app.py`, cambiar:

```python
allow_origins=["*"],  # Permitir todo (desarrollo)
```

Por:

```python
allow_origins=[
    "https://tu-dominio.com",
    "https://dashboard.tu-dominio.com"
],  # Solo dominios específicos
```

### 3. Usar Variables de Entorno Seguras

Nunca commitear `.env` con credenciales reales. Usar servicios de gestión de secretos:
- AWS Secrets Manager
- HashiCorp Vault
- Variables de entorno del servicio de hosting

## 📊 Monitoreo y Logs

### Ver logs en Docker Compose

```bash
docker-compose -f docker-compose.prod.yml logs -f api
docker-compose -f docker-compose.prod.yml logs -f dashboard
```

### Ver logs sin Docker

```bash
tail -f logs/aria.log
```

### Monitoreo con PM2 (Recomendado)

```bash
npm install -g pm2

# Iniciar API
pm2 start "aria api --host 0.0.0.0 --port 8000" --name aria-api

# Iniciar Dashboard
cd dashboard
pm2 start "npm run dev -- --host 0.0.0.0" --name aria-dashboard

# Ver estado
pm2 status

# Ver logs
pm2 logs aria-api
```

## 🚀 Scripts de Inicio Rápido

### Script para Servidor Cloud

```bash
#!/bin/bash
# start-aria-cloud.sh

cd /ruta/a/ARIA

# Activar entorno virtual
source venv/bin/activate

# Iniciar API en background
nohup aria api --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &

# Iniciar Dashboard en background
cd dashboard
nohup npm run dev -- --host 0.0.0.0 > ../logs/dashboard.log 2>&1 &

echo "ARIA iniciado en:"
echo "  API: http://$(hostname -I | awk '{print $1}'):8000"
echo "  Dashboard: http://$(hostname -I | awk '{print $1}'):5173"
```

## 🔍 Verificación

Después del despliegue, verificar:

1. **API funcionando:**
   ```bash
   curl http://TU_IP:8000/health
   ```

2. **Dashboard accesible:**
   Abrir en navegador: `http://TU_IP:5173`

3. **CORS configurado:**
   Verificar que el dashboard puede hacer requests a la API

## 📝 Notas Importantes

- **Puerto 8000**: Debe estar abierto para la API
- **Puerto 5173**: Debe estar abierto para el dashboard (o usar reverse proxy)
- **Redis**: Puede ejecutarse en el mismo servidor o como servicio separado
- **Firewall**: Configurar reglas para permitir tráfico en los puertos necesarios
- **Dominio**: Opcional pero recomendado para producción

## 🆘 Solución de Problemas

### El dashboard no puede conectarse a la API

1. Verificar que la API esté corriendo: `curl http://localhost:8000/health`
2. Verificar firewall: `sudo ufw status`
3. Verificar CORS en `aria/api/app.py`
4. Verificar `VITE_API_URL` en el dashboard

### Error de conexión a Redis

1. Verificar que Redis esté corriendo: `redis-cli ping`
2. Verificar `REDIS_URL` en `.env`
3. Si usas Docker, verificar que el contenedor esté corriendo

### Puerto ya en uso

```bash
# Ver qué proceso usa el puerto
sudo lsof -i :8000

# Detener proceso
sudo kill -9 <PID>
```
