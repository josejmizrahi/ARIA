# 🤖 Sistema de Comunicación y Aprendizaje entre Agentes

## 📋 Resumen

Los agentes de ARIA ahora pueden:
- **Comunicarse entre sí** para colaborar en la resolución de problemas
- **Validar datos** antes de usarlos mediante introspección automática
- **Aprender de logs** para mejorar sus decisiones
- **Colaborar** para resolver problemas complejos

## 🔄 Flujo de Comunicación

### Ejemplo: Agente de Finanzas consulta a Agente de Cobranza

```
┌─────────────────┐
│ Finance Agent   │
│ (Proyecta flujo)│
└────────┬────────┘
         │
         │ 1. Introspección: Valida campos de account.move
         ▼
    ¿Campos válidos?
         │
         ├─ NO → Usa solo campos válidos + loguea advertencia
         │
         └─ SÍ → Continúa
         │
         │ 2. Envía mensaje a Cobranza
         ▼
┌─────────────────┐
│ Receivables     │
│ Agent           │
└────────┬────────┘
         │
         │ 3. Procesa mensaje pendiente
         │
         │ 4. Calcula proyección de cobranza
         │
         │ 5. Responde con datos
         ▼
┌─────────────────┐
│ Finance Agent   │
│ (Recibe datos)  │
└─────────────────┘
```

## 🔍 Introspección Automática

### Antes de cada consulta crítica:

```python
# El agente valida automáticamente:
validation = self.introspection.validate_query(
    model="account.move",
    fields=["amount_residual", "invoice_date_due", "move_type"]
)

# Resultado:
{
    "valid": True/False,
    "model_exists": True/False,
    "fields_valid": {
        "amount_residual": True,
        "invoice_date_due": True,
        "move_type": False  # Campo no existe
    },
    "missing_fields": ["move_type"],
    "suggestions": {
        "move_type": "move_type_id"  # Campo alternativo sugerido
    }
}
```

### Si hay campos inválidos:

1. **Usa solo campos válidos** automáticamente
2. **Loguea advertencia** con campos faltantes
3. **Sugiere alternativas** si las encuentra
4. **Aprende del patrón** para futuras consultas

## 💬 Tipos de Mensajes

### 1. Query (Pregunta)

```python
# Agente A pregunta a Agente B
await self.ask_agent(
    to_agent="cobranza",
    question="¿Cuál es la proyección de cobranza para las próximas 4 semanas?",
    data={"weeks": 4, "company_id": 1},
    priority="medium"
)
```

### 2. Alert (Alerta)

```python
# Agente A alerta a Agente B sobre un problema
await self.alert_agent(
    to_agent="finanzas",
    alert_subject="Déficit de caja proyectado",
    alert_content="Se proyecta déficit en las próximas 2 semanas",
    data={"deficit_amount": 500000, "weeks": [1, 2]},
    priority="critical"
)
```

### 3. Data Request (Solicitud de Datos)

```python
# Agente A solicita datos específicos
await self.request_data_from_agent(
    to_agent="ventas",
    data_request="Ingresos del mes actual",
    fields=["amount_total", "invoice_date"],
    filters={"state": "posted", "move_type": "out_invoice"}
)
```

### 4. Response (Respuesta)

```python
# Agente B responde a una pregunta
await self.respond_to_agent(
    message_id="abc123",
    response="La proyección de cobranza es $2,500,000",
    data={"total": 2500000, "by_week": {...}}
)
```

## 🧠 Sistema de Aprendizaje

### Aprende de Logs

El sistema analiza los logs para extraer:

1. **Errores de campos:**
   ```
   Campo 'move_type' no existe → Sugerencia: usar 'move_type_id'
   ```

2. **Soluciones exitosas:**
   ```
   Usando solo campos válidos: ['amount_total', 'invoice_date']
   ```

3. **Patrones de datos:**
   ```
   Modelo account.move siempre requiere 'company_id' en filtros
   ```

### Registra Éxitos y Fracasos

```python
# Cuando una tarea tiene éxito:
self.learning.record_success(
    agent_name="finanzas",
    pattern_type="task_cash_flow_projection",
    context={"task": "cash_flow_projection"}
)

# Cuando una tarea falla:
self.learning.record_failure(
    agent_name="finanzas",
    pattern_type="task_cash_flow_projection",
    context={"task": "cash_flow_projection", "error": "..."}
)
```

### Usa Soluciones Aprendidas

```python
# Buscar solución aprendida:
solution = self.learning.get_solution(
    agent_name="finanzas",
    problem_type="field_mapping",
    context={"field": "move_type"}
)

# Si existe solución:
if solution:
    use_field = solution.get("use_field")  # "move_type_id"
```

## 📊 Ejemplo Completo: Colaboración Finanzas ↔ Cobranza

### Paso 1: Finanzas necesita datos

```python
# En finance_agent.py - project_cash_flow()
async def project_cash_flow(self):
    # Introspección automática
    validation = self.introspection.validate_query(
        "account.move",
        ["amount_residual", "invoice_date_due"]
    )
    
    # Consultar a cobranza
    await self.alert_agent(
        to_agent="cobranza",
        alert_subject="Consulta: Proyección de cobranza",
        alert_content="Necesito proyección para 4 semanas",
        data={"weeks": 4, "company_id": self.company_id}
    )
```

### Paso 2: Cobranza procesa y responde

```python
# En receivables_agent.py - _process_pending_messages()
async def _process_pending_messages(self):
    messages = self.check_messages(unread_only=True)
    
    for msg in messages:
        if msg["message_type"] == "alert" and "cobranza" in msg["content"]:
            # Calcular proyección
            weeks = msg["data"]["weeks"]
            total = self._calculate_collections_projection(weeks)
            
            # Responder
            await self.respond_to_agent(
                message_id=msg["id"],
                response=f"Proyección: {self.format_currency(total)}",
                data={"total": total, "by_week": {...}}
            )
```

### Paso 3: Finanzas usa la respuesta

```python
# Finanzas puede consultar la respuesta:
messages = self.check_messages()
for msg in messages:
    if msg["response_to"] == original_message_id:
        projection_data = msg["data"]
        # Usar datos para proyección
```

## 🎯 Validación Automática en search_read

Ahora `search_read` valida automáticamente:

```python
# Antes (sin validación):
invoices = self.search_read(
    "account.move",
    [("state", "=", "posted")],
    ["amount_total", "move_type"]  # move_type puede no existir
)

# Ahora (con validación automática):
invoices = self.search_read(
    "account.move",
    [("state", "=", "posted")],
    ["amount_total", "move_type"],
    validate=True  # Valida campos antes de consultar
)

# Si move_type no existe:
# - Usa solo amount_total
# - Loguea advertencia
# - Sugiere alternativa si existe
# - Aprende el patrón
```

## 📱 Dashboard de Conversaciones

Accede desde el dashboard principal:
- Click en botón "Conversaciones"
- O directamente: `/conversations`

Verás:
- **Conversaciones completas** entre agentes
- **Mensajes individuales** con prioridad y tipo
- **Respuestas** y colaboraciones
- **Filtros** por agente

## 🔧 Endpoints API

### Mensajes

```bash
# Ver todos los mensajes
GET /api/agents/messages

# Filtrar por agente
GET /api/agents/messages?agent_name=finanzas

# Solo no leídos
GET /api/agents/messages?unread_only=true

# Ver conversación completa
GET /api/agents/messages/{message_id}

# Responder a mensaje
POST /api/agents/messages/{message_id}/respond?agent_name=cobranza&response=...
```

### Conversaciones

```bash
# Listar todas las conversaciones
GET /api/agents/conversations

# Filtrar por agente
GET /api/agents/conversations?agent_name=finanzas
```

### Aprendizaje

```bash
# Ver patrones aprendidos
GET /api/agents/learning

# Filtrar por agente
GET /api/agents/learning?agent_name=finanzas

# Forzar aprendizaje desde logs
POST /api/agents/learning/learn-from-logs?agent_name=finanzas
```

## 🎓 Cómo los Agentes se Vuelven Más Inteligentes

### 1. Introspección → Datos Correctos

```
Primera vez:
- Intenta usar campo "move_type"
- Campo no existe
- Usa solo campos válidos
- Aprende: "move_type" no existe en account.move

Segunda vez:
- Busca solución aprendida
- Encuentra: usar "move_type_id" en su lugar
- Usa campo correcto desde el inicio
```

### 2. Colaboración → Datos Más Precisos

```
Finanzas necesita proyección:
- Consulta directamente a Cobranza (experto)
- Cobranza calcula con su lógica especializada
- Finanzas recibe datos precisos
- Ambos aprenden del intercambio
```

### 3. Aprendizaje de Logs → Mejora Continua

```
El sistema analiza logs diariamente:
- Encuentra errores comunes
- Extrae soluciones exitosas
- Crea patrones de aprendizaje
- Los agentes usan estos patrones automáticamente
```

## 📈 Ejemplo Práctico: Resolución de Problema

### Problema Detectado

```
Finanzas detecta: Déficit de caja proyectado
```

### Proceso de Resolución

1. **Finanzas → Cobranza:**
   ```
   "¿Puedes acelerar cobranza para las próximas 2 semanas?"
   ```

2. **Cobranza analiza:**
   ```
   - Revisa facturas vencidas
   - Identifica clientes prioritarios
   - Calcula cobranza acelerable
   ```

3. **Cobranza → Finanzas:**
   ```
   "Puedo acelerar $500,000 en los próximos 7 días"
   ```

4. **Finanzas recalcula:**
   ```
   - Usa datos de Cobranza
   - Recalcula proyección
   - Verifica si resuelve el déficit
   ```

5. **Finanzas → CEO:**
   ```
   "Déficit resuelto con aceleración de cobranza"
   ```

## 🔐 Validación de Datos

### Antes de usar cualquier campo:

```python
# Validación automática
fields = ["amount_total", "invoice_date", "move_type"]
validation = self.introspection.validate_query("account.move", fields)

if not validation["valid"]:
    # Usar solo campos válidos
    valid_fields = [f for f, v in validation["fields_valid"].items() if v]
    # Aprender del error
    self.learning.add_pattern(
        agent_name=self.name,
        pattern_type="field_mapping",
        context={"model": "account.move", "invalid_field": "move_type"},
        solution={"use_fields": valid_fields}
    )
```

## 📝 Logs Estructurados

Los agentes loguean:

```python
# Introspección
INFO: Validando campos de account.move: ['amount_total', 'move_type']
WARNING: Campo 'move_type' no existe. Usando solo campos válidos: ['amount_total']

# Comunicación
INFO: Mensaje enviado: finanzas → cobranza: Consulta proyección de cobranza
INFO: Respondido a finanzas sobre proyección de cobranza

# Aprendizaje
INFO: Patrón aprendido: field_mapping para account.move
INFO: Usando solución aprendida: usar 'move_type_id' en lugar de 'move_type'
```

## 🚀 Beneficios

1. **Datos Fiables:** Validación automática antes de usar
2. **Colaboración:** Agentes trabajan juntos
3. **Aprendizaje:** Mejoran con el tiempo
4. **Trazabilidad:** Puedes ver todas las conversaciones
5. **Resolución Inteligente:** Problemas complejos se resuelven colaborativamente

## 🎯 Próximos Pasos

Los agentes pueden:
- Consultar a múltiples agentes simultáneamente
- Aprender de decisiones exitosas
- Compartir conocimiento entre agentes
- Validar datos antes de tomar decisiones críticas
- Colaborar para resolver problemas complejos

¡El sistema se vuelve más inteligente con cada ejecución!
