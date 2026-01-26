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
  Receipt,
  Wallet,
  Calculator,
  UserCog,
  Bot,
  Settings,
  Target,
  PiggyBank,
  MessageSquare
} from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { KPICard } from "@/components/kpi-card"
import { AgentCard } from "@/components/agent-card"
import { ProposalCard } from "@/components/proposal-card"
import FinanceDashboard from './FinanceDashboard'
import AgentConversations from './AgentConversations'

const API_BASE = '/api'

// Agent icon mapping
const AGENT_ICONS = {
  ceo: Bot,
  cobranza: Receipt,
  ventas: TrendingUp,
  compras: Package,
  finanzas: Wallet,
  contabilidad: Calculator,
  inventario: Package,
  rrhh: UserCog,
  produccion: Activity,
  sistema: Settings,
  crm: Target,
  costos: PiggyBank,
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

export default function App() {
  const [dashboard, setDashboard] = useState(null)
  const [agents, setAgents] = useState([])
  const [proposals, setProposals] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [error, setError] = useState(null)
  const [showFinanceDashboard, setShowFinanceDashboard] = useState(false)
  const [showConversations, setShowConversations] = useState(false)
  const [companies, setCompanies] = useState([])
  const [selectedCompany, setSelectedCompany] = useState(null)
  
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
    fetch(`${API_BASE}/companies`)
      .then(res => res.json())
      .then(data => {
        const companies = data.companies || []
        setCompanies(companies)
        
        if (companies.length > 0) {
          // Buscar company_id = 1 primero (comparar como número y string)
          const companyId1 = companies.find(c => {
            const id = parseInt(c.id)
            return id === 1
          })
          
          if (companyId1) {
            console.log('✅ Seleccionando empresa por defecto:', companyId1.name, 'ID:', companyId1.id)
            setSelectedCompany(parseInt(companyId1.id))
          } else {
            // Si no existe id=1, usar la primera disponible
            console.warn('⚠️ No se encontró empresa con ID=1. Empresas disponibles:', companies.map(c => `${c.name} (ID: ${c.id})`))
            console.log('Usando primera disponible:', companies[0].name, 'ID:', companies[0].id)
            setSelectedCompany(parseInt(companies[0].id))
          }
        }
      })
      .catch(err => console.error('Error cargando compañías:', err))
  }, [])
  
  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [fetchData, selectedCompany])
  
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
        <Card className="w-96">
          <CardHeader>
            <div className="flex items-center justify-center">
              <Zap className="w-16 h-16 text-primary animate-pulse" />
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-center text-muted-foreground">Cargando ARIA...</p>
          </CardContent>
        </Card>
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card className="w-96">
          <CardHeader>
            <div className="flex items-center justify-center mb-4">
              <AlertTriangle className="w-16 h-16 text-destructive" />
            </div>
            <CardTitle className="text-center">Error de conexión</CardTitle>
            <CardDescription className="text-center">{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={fetchData} className="w-full">
              Reintentar
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }
  
  const pendingByPriority = dashboard?.pending_proposals?.by_priority || {}
  const criticalCount = pendingByPriority.critical || 0
  const highCount = pendingByPriority.high || 0
  const totalPending = dashboard?.pending_proposals?.total || 0
  
  // Si se muestra el dashboard de conversaciones
  if (showConversations) {
    return (
      <div className="min-h-screen bg-background">
        <header className="sticky top-0 z-50 border-b bg-card">
          <div className="container mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary rounded-lg">
                  <Zap className="w-6 h-6 text-primary-foreground" />
                </div>
                <div>
                  <h1 className="text-xl font-bold">ARIA</h1>
                  <p className="text-xs text-muted-foreground">Conversaciones entre Agentes</p>
                </div>
              </div>
              <Button variant="outline" onClick={() => setShowConversations(false)}>
                Volver al Dashboard
              </Button>
            </div>
          </div>
        </header>
        <main className="container mx-auto px-6 py-8">
          <AgentConversations />
        </main>
      </div>
    )
  }
  
  // Si se muestra el dashboard financiero
  if (showFinanceDashboard) {
    return (
      <div className="min-h-screen bg-background">
        <header className="sticky top-0 z-50 border-b bg-card">
          <div className="container mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary rounded-lg">
                  <Zap className="w-6 h-6 text-primary-foreground" />
                </div>
                <div>
                  <h1 className="text-xl font-bold">ARIA</h1>
                  <p className="text-xs text-muted-foreground">Planeación Financiera</p>
                </div>
              </div>
              <Button variant="outline" onClick={() => setShowFinanceDashboard(false)}>
                Volver al Dashboard
              </Button>
            </div>
          </div>
        </header>
        <main className="container mx-auto px-6 py-8">
          <FinanceDashboard />
        </main>
      </div>
    )
  }
  
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary rounded-lg">
                <Zap className="w-6 h-6 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-xl font-bold">ARIA</h1>
                <p className="text-xs text-muted-foreground">Autonomous Resource Intelligence Agent</p>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              {companies.length > 1 && (
                <Select value={selectedCompany?.toString()} onValueChange={(v) => setSelectedCompany(parseInt(v))}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Seleccionar empresa" />
                  </SelectTrigger>
                  <SelectContent>
                    {companies
                      .filter(comp => comp.id === 1) // Solo mostrar empresa con ID=1
                      .map(comp => (
                        <SelectItem key={comp.id} value={comp.id.toString()}>
                          {comp.name}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              )}
              {companies.length === 1 && companies[0].id === 1 && (
                <div className="text-sm text-muted-foreground">
                  {companies[0].name}
                </div>
              )}
              <Button variant="outline" onClick={() => setShowConversations(true)}>
                <MessageSquare className="w-4 h-4 mr-2" />
                Conversaciones
              </Button>
              {lastUpdate && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Clock className="w-4 h-4" />
                  {lastUpdate.toLocaleTimeString()}
                </div>
              )}
              <Button variant="ghost" size="icon" onClick={fetchData}>
                <RefreshCw className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </header>
      
      <main className="container mx-auto px-6 py-8 space-y-8">
        {/* Alert Banner */}
        {criticalCount > 0 && (
          <Card className="border-destructive bg-destructive/10">
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <AlertTriangle className="w-8 h-8 text-destructive shrink-0" />
                <div>
                  <p className="font-semibold text-destructive">
                    {criticalCount} propuesta{criticalCount > 1 ? 's' : ''} crítica{criticalCount > 1 ? 's' : ''} requiere{criticalCount > 1 ? 'n' : ''} atención
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Revisa las alertas para evitar problemas operativos
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
        
        {/* KPIs */}
        <section>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
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
              subtitle={`Runway: ${Math.round(dashboard?.agents?.finanzas?.runway_days || 0)} días • Click para ver análisis completo`}
              icon={Wallet}
              status={dashboard?.agents?.finanzas?.status}
              onClick={() => setShowFinanceDashboard(true)}
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
              <Users className="w-5 h-5" />
              Agentes
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Object.entries(dashboard?.agents || {}).map(([name, data]) => {
                const Icon = AGENT_ICONS[name] || Activity
                return (
                  <AgentCard
                    key={name}
                    name={name}
                    data={data}
                    icon={Icon}
                    onClick={() => {
                      if (name === 'finanzas') {
                        setShowFinanceDashboard(true)
                      }
                    }}
                  />
                )
              })}
            </div>
          </section>
          
          {/* Proposals */}
          <section>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5" />
              Propuestas Pendientes
              {totalPending > 0 && (
                <span className="ml-auto text-sm px-2 py-0.5 rounded-full bg-primary/20 text-primary">
                  {totalPending}
                </span>
              )}
            </h2>
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-3 max-h-[600px] overflow-y-auto">
                  {proposals.length > 0 ? (
                    proposals.slice(0, 10).map((proposal) => (
                      <ProposalCard
                        key={proposal.id}
                        proposal={proposal}
                        onApprove={handleApprove}
                        onReject={handleReject}
                      />
                    ))
                  ) : (
                    <div className="text-center py-8">
                      <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
                      <p className="text-muted-foreground">Sin propuestas pendientes</p>
                      <p className="text-sm text-muted-foreground mt-1">Todo está bajo control</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </section>
        </div>
      </main>
      
      {/* Footer */}
      <footer className="border-t mt-8">
        <div className="container mx-auto px-6 py-4">
          <p className="text-center text-sm text-muted-foreground">
            ARIA v0.1.0 • Autonomous Resource Intelligence Agent
          </p>
        </div>
      </footer>
    </div>
  )
}
