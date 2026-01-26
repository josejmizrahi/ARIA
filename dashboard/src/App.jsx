import { useState, useEffect, useCallback } from 'react'
import { 
  Activity, 
  Users, 
  Package, 
  DollarSign, 
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  RefreshCw,
  Zap,
  BarChart3,
  Boxes,
  Receipt,
  Wallet,
  Calculator,
  UserCog,
  Bot,
  Settings,
  Target,
  PiggyBank
} from 'lucide-react'

const API_BASE = '/api'

// Agent icon mapping
const AGENT_ICONS = {
  ceo: Bot,
  cobranza: Receipt,
  ventas: TrendingUp,
  compras: Package,
  finanzas: Wallet,
  contabilidad: Calculator,
  inventario: Boxes,
  rrhh: UserCog,
  produccion: Activity,
  sistema: Settings,
  crm: Target,
  costos: PiggyBank,
}

// Status colors
const STATUS_COLORS = {
  critical: 'status-critical',
  warning: 'status-warning',
  ok: 'status-ok',
  error: 'status-critical',
}

function formatCurrency(value) {
  if (value === undefined || value === null) return '-'
  return new Intl.NumberFormat('es-MX', { 
    style: 'currency', 
    currency: 'MXN',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

function formatNumber(value) {
  if (value === undefined || value === null) return '-'
  return new Intl.NumberFormat('es-MX').format(value)
}

// KPI Card Component
function KPICard({ title, value, subtitle, icon: Icon, status, trend }) {
  return (
    <div className={`glass rounded-2xl p-6 animate-fade-in ${status ? STATUS_COLORS[status] : ''}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-surface-400 text-sm font-medium mb-1">{title}</p>
          <p className="text-3xl font-bold font-mono tracking-tight">{value}</p>
          {subtitle && (
            <p className="text-surface-500 text-sm mt-1">{subtitle}</p>
          )}
        </div>
        {Icon && (
          <div className={`p-3 rounded-xl ${status ? '' : 'bg-aria-500/20'}`}>
            <Icon className={`w-6 h-6 ${status ? '' : 'text-aria-400'}`} />
          </div>
        )}
      </div>
      {trend !== undefined && (
        <div className={`mt-4 flex items-center gap-1 text-sm ${trend >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          <TrendingUp className={`w-4 h-4 ${trend < 0 ? 'rotate-180' : ''}`} />
          <span>{Math.abs(trend).toFixed(1)}% vs periodo anterior</span>
        </div>
      )}
    </div>
  )
}

// Agent Status Card
function AgentCard({ name, data, onClick }) {
  const Icon = AGENT_ICONS[name] || Activity
  const status = data?.status || 'ok'
  
  return (
    <button 
      onClick={onClick}
      className={`glass rounded-xl p-4 text-left w-full hover:scale-[1.02] transition-all duration-200 animate-slide-up border ${STATUS_COLORS[status]}`}
    >
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-lg ${status === 'ok' ? 'bg-emerald-500/20' : status === 'warning' ? 'bg-amber-500/20' : 'bg-red-500/20'}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <h3 className="font-semibold capitalize">{name}</h3>
          <p className="text-xs text-surface-500">Agente autónomo</p>
        </div>
        <div className={`ml-auto w-2 h-2 rounded-full ${status === 'ok' ? 'bg-emerald-500' : status === 'warning' ? 'bg-amber-500' : 'bg-red-500'} animate-pulse`} />
      </div>
      
      {data && (
        <div className="space-y-2 text-sm">
          {data.cash_balance !== undefined && (
            <div className="flex justify-between">
              <span className="text-surface-400">Saldo</span>
              <span className="font-mono">{formatCurrency(data.cash_balance)}</span>
            </div>
          )}
          {data.total_overdue !== undefined && (
            <div className="flex justify-between">
              <span className="text-surface-400">Vencido</span>
              <span className="font-mono text-red-400">{formatCurrency(data.total_overdue)}</span>
            </div>
          )}
          {data.active_employees !== undefined && (
            <div className="flex justify-between">
              <span className="text-surface-400">Empleados</span>
              <span className="font-mono">{data.active_employees}</span>
            </div>
          )}
          {data.total_products !== undefined && (
            <div className="flex justify-between">
              <span className="text-surface-400">Productos</span>
              <span className="font-mono">{formatNumber(data.total_products)}</span>
            </div>
          )}
        </div>
      )}
    </button>
  )
}

// Proposal Card
function ProposalCard({ proposal, onApprove, onReject }) {
  const priorityColors = {
    critical: 'border-l-red-500 bg-red-500/5',
    high: 'border-l-amber-500 bg-amber-500/5',
    medium: 'border-l-blue-500 bg-blue-500/5',
    low: 'border-l-surface-500 bg-surface-500/5',
  }
  
  const priority = proposal.priority?.toLowerCase() || 'medium'
  
  return (
    <div className={`glass rounded-xl p-4 border-l-4 ${priorityColors[priority]} animate-slide-up`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs px-2 py-0.5 rounded-full bg-surface-800 text-surface-400">
              {proposal.agent_name}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${
              priority === 'critical' ? 'bg-red-500/20 text-red-400' :
              priority === 'high' ? 'bg-amber-500/20 text-amber-400' :
              'bg-blue-500/20 text-blue-400'
            }`}>
              {priority}
            </span>
          </div>
          <h4 className="font-medium truncate">{proposal.title}</h4>
          <p className="text-sm text-surface-400 mt-1 line-clamp-2">
            {proposal.description || proposal.situation_summary?.slice(0, 100)}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button 
            onClick={() => onApprove(proposal.id)}
            className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors"
          >
            <CheckCircle2 className="w-5 h-5" />
          </button>
          <button 
            onClick={() => onReject(proposal.id)}
            className="p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
          >
            <AlertTriangle className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  )
}

// Main Dashboard
export default function App() {
  const [dashboard, setDashboard] = useState(null)
  const [agents, setAgents] = useState([])
  const [proposals, setProposals] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [error, setError] = useState(null)
  
  const fetchData = useCallback(async () => {
    try {
      setError(null)
      
      const [dashRes, agentsRes, proposalsRes] = await Promise.all([
        fetch(`${API_BASE}/dashboard`),
        fetch(`${API_BASE}/agents`),
        fetch(`${API_BASE}/proposals?status=pending`),
      ])
      
      if (!dashRes.ok || !agentsRes.ok || !proposalsRes.ok) {
        throw new Error('Error fetching data')
      }
      
      const [dashData, agentsData, proposalsData] = await Promise.all([
        dashRes.json(),
        agentsRes.json(),
        proposalsRes.json(),
      ])
      
      setDashboard(dashData)
      setAgents(agentsData.agents || [])
      setProposals(proposalsData.proposals || [])
      setLastUpdate(new Date())
    } catch (err) {
      console.error('Error fetching data:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])
  
  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [fetchData])
  
  const handleApprove = async (id) => {
    try {
      await fetch(`${API_BASE}/proposals/${id}/approve`, { method: 'POST' })
      fetchData()
    } catch (err) {
      console.error('Error approving:', err)
    }
  }
  
  const handleReject = async (id) => {
    try {
      await fetch(`${API_BASE}/proposals/${id}/reject`, { method: 'POST' })
      fetchData()
    } catch (err) {
      console.error('Error rejecting:', err)
    }
  }
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Zap className="w-16 h-16 text-aria-500 mx-auto animate-pulse" />
          <p className="mt-4 text-surface-400">Cargando ARIA...</p>
        </div>
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center glass rounded-2xl p-8 max-w-md">
          <AlertTriangle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">Error de conexión</h2>
          <p className="text-surface-400 mb-4">{error}</p>
          <button 
            onClick={fetchData}
            className="px-6 py-2 bg-aria-600 rounded-lg hover:bg-aria-700 transition-colors"
          >
            Reintentar
          </button>
        </div>
      </div>
    )
  }
  
  const pendingByPriority = dashboard?.pending_proposals?.by_priority || {}
  const criticalCount = pendingByPriority.critical || 0
  const highCount = pendingByPriority.high || 0
  const totalPending = dashboard?.pending_proposals?.total || 0
  
  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-50 glass border-b border-surface-800/50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-aria-500 to-aria-700 rounded-xl">
                <Zap className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight">ARIA</h1>
                <p className="text-xs text-surface-500">Autonomous Resource Intelligence Agent</p>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              {lastUpdate && (
                <span className="text-sm text-surface-500 flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  {lastUpdate.toLocaleTimeString()}
                </span>
              )}
              <button 
                onClick={fetchData}
                className="p-2 rounded-lg bg-surface-800 hover:bg-surface-700 transition-colors"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>
      
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Alert Banner */}
        {criticalCount > 0 && (
          <div className="glass rounded-2xl p-4 border border-red-500/30 bg-red-500/10 flex items-center gap-4 animate-pulse-slow glow-critical">
            <AlertTriangle className="w-8 h-8 text-red-500 shrink-0" />
            <div>
              <p className="font-semibold text-red-400">
                {criticalCount} propuesta{criticalCount > 1 ? 's' : ''} crítica{criticalCount > 1 ? 's' : ''} requiere{criticalCount > 1 ? 'n' : ''} atención
              </p>
              <p className="text-sm text-surface-400">
                Revisa las alertas para evitar problemas operativos
              </p>
            </div>
          </div>
        )}
        
        {/* KPIs */}
        <section>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-aria-500" />
            Indicadores Clave
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              title="Propuestas Pendientes"
              value={totalPending}
              subtitle={criticalCount > 0 ? `${criticalCount} críticas` : 'Todo en orden'}
              icon={Clock}
              status={criticalCount > 0 ? 'critical' : highCount > 0 ? 'warning' : 'ok'}
            />
            <KPICard
              title="Agentes Activos"
              value={agents.length}
              subtitle="Monitoreando operaciones"
              icon={Bot}
            />
            <KPICard
              title="Saldo Bancario"
              value={formatCurrency(dashboard?.agents?.finanzas?.cash_balance)}
              subtitle={`Runway: ${Math.round(dashboard?.agents?.finanzas?.runway_days || 0)} días`}
              icon={Wallet}
              status={dashboard?.agents?.finanzas?.status}
            />
            <KPICard
              title="CxC Vencidas"
              value={formatCurrency(dashboard?.agents?.cobranza?.total_overdue)}
              subtitle={`DSO: ${Math.round(dashboard?.agents?.cobranza?.dso || 0)} días`}
              icon={Receipt}
              status={dashboard?.agents?.cobranza?.status}
            />
          </div>
        </section>
        
        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Agents */}
          <section className="lg:col-span-2">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-aria-500" />
              Agentes
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Object.entries(dashboard?.agents || {}).map(([name, data], i) => (
                <div key={name} className={`stagger-${i % 5 + 1}`}>
                  <AgentCard 
                    name={name} 
                    data={data}
                    onClick={() => console.log('Agent clicked:', name)}
                  />
                </div>
              ))}
            </div>
          </section>
          
          {/* Proposals */}
          <section>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-aria-500" />
              Propuestas Pendientes
              {totalPending > 0 && (
                <span className="ml-auto text-sm px-2 py-0.5 rounded-full bg-aria-500/20 text-aria-400">
                  {totalPending}
                </span>
              )}
            </h2>
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
              {proposals.length > 0 ? (
                proposals.slice(0, 10).map((proposal, i) => (
                  <div key={proposal.id} className={`stagger-${i % 5 + 1}`}>
                    <ProposalCard 
                      proposal={proposal}
                      onApprove={handleApprove}
                      onReject={handleReject}
                    />
                  </div>
                ))
              ) : (
                <div className="glass rounded-xl p-8 text-center">
                  <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
                  <p className="text-surface-400">Sin propuestas pendientes</p>
                  <p className="text-sm text-surface-500 mt-1">Todo está bajo control</p>
                </div>
              )}
            </div>
          </section>
        </div>
      </main>
      
      {/* Footer */}
      <footer className="border-t border-surface-800/50 mt-8">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <p className="text-center text-sm text-surface-500">
            ARIA v0.1.0 • Autonomous Resource Intelligence Agent
          </p>
        </div>
      </footer>
    </div>
  )
}
