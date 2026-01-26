import { useState, useEffect } from 'react'
import { 
  TrendingUp, 
  TrendingDown, 
  DollarSign, 
  BarChart3,
  PieChart,
  Target,
  AlertTriangle,
  CheckCircle2,
  Wallet,
  Calculator
} from 'lucide-react'

const API_BASE = '/api'

function formatCurrency(value) {
  if (value === undefined || value === null) return '-'
  return new Intl.NumberFormat('es-MX', { 
    style: 'currency', 
    currency: 'MXN',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

function formatPercent(value) {
  if (value === undefined || value === null) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

// Metric Card Component
function MetricCard({ title, value, subtitle, icon: Icon, trend, status }) {
  const statusColors = {
    ok: 'border-emerald-500/30 bg-emerald-500/10',
    warning: 'border-amber-500/30 bg-amber-500/10',
    critical: 'border-red-500/30 bg-red-500/10',
  }
  
  return (
    <div className={`glass rounded-xl p-6 border ${statusColors[status] || 'border-surface-800'}`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-surface-400 text-sm font-medium mb-1">{title}</p>
          <p className="text-2xl font-bold font-mono">{value}</p>
          {subtitle && (
            <p className="text-surface-500 text-sm mt-1">{subtitle}</p>
          )}
        </div>
        {Icon && (
          <div className={`p-3 rounded-lg ${statusColors[status] || 'bg-aria-500/20'}`}>
            <Icon className={`w-5 h-5 ${status === 'ok' ? 'text-emerald-400' : status === 'warning' ? 'text-amber-400' : status === 'critical' ? 'text-red-400' : 'text-aria-400'}`} />
          </div>
        )}
      </div>
      {trend !== undefined && (
        <div className={`flex items-center gap-1 text-sm ${trend >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {trend >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          <span>{formatPercent(trend)}</span>
        </div>
      )}
    </div>
  )
}

// Simple Bar Chart Component
function SimpleBarChart({ data, title }) {
  if (!data || data.length === 0) {
    return (
      <div className="glass rounded-xl p-8 text-center">
        <p className="text-surface-500">No hay datos disponibles</p>
      </div>
    )
  }
  
  const maxValue = Math.max(...data.map(d => d.value))
  
  return (
    <div className="glass rounded-xl p-6">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <div className="space-y-3">
        {data.map((item, i) => (
          <div key={i}>
            <div className="flex justify-between mb-1">
              <span className="text-sm text-surface-400 truncate">{item.label}</span>
              <span className="text-sm font-mono">{formatCurrency(item.value)}</span>
            </div>
            <div className="h-2 bg-surface-800 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-aria-500 to-aria-600 rounded-full transition-all"
                style={{ width: `${(item.value / maxValue) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Budget Comparison Component
function BudgetComparison({ data }) {
  if (!data) return null
  
  const { actual_revenue, expected_revenue, revenue_variance_pct, actual_expenses, expected_expenses, expense_variance_pct } = data
  
  return (
    <div className="glass rounded-xl p-6">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Target className="w-5 h-5 text-aria-500" />
        Comparativo vs Presupuesto
      </h3>
      
      <div className="space-y-4">
        <div>
          <div className="flex justify-between mb-2">
            <span className="text-sm text-surface-400">Ingresos</span>
            <span className={`text-sm font-semibold ${revenue_variance_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {formatPercent(revenue_variance_pct)}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <p className="text-surface-500">Real</p>
              <p className="font-mono">{formatCurrency(actual_revenue)}</p>
            </div>
            <div>
              <p className="text-surface-500">Esperado</p>
              <p className="font-mono">{formatCurrency(expected_revenue)}</p>
            </div>
          </div>
        </div>
        
        <div>
          <div className="flex justify-between mb-2">
            <span className="text-sm text-surface-400">Gastos</span>
            <span className={`text-sm font-semibold ${expense_variance_pct <= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {formatPercent(expense_variance_pct)}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <p className="text-surface-500">Real</p>
              <p className="font-mono">{formatCurrency(actual_expenses)}</p>
            </div>
            <div>
              <p className="text-surface-500">Esperado</p>
              <p className="font-mono">{formatCurrency(expected_expenses)}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function FinanceDashboard() {
  const [summary, setSummary] = useState(null)
  const [ratios, setRatios] = useState(null)
  const [budget, setBudget] = useState(null)
  const [profitability, setProfitability] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  
  useEffect(() => {
    fetchFinanceData()
    const interval = setInterval(fetchFinanceData, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])
  
  const fetchFinanceData = async () => {
    try {
      const [summaryRes, ratiosRes, budgetRes, profitabilityRes, forecastRes] = await Promise.all([
        fetch(`${API_BASE}/agents/finanzas/summary`),
        fetch(`${API_BASE}/finance/ratios`).catch(() => null),
        fetch(`${API_BASE}/finance/budget`).catch(() => null),
        fetch(`${API_BASE}/finance/profitability`).catch(() => null),
        fetch(`${API_BASE}/finance/forecast`).catch(() => null),
      ])
      
      if (summaryRes.ok) {
        const summaryData = await summaryRes.json()
        setSummary(summaryData)
      }
      
      if (ratiosRes?.ok) {
        const ratiosData = await ratiosRes.json()
        setRatios(ratiosData.data)
      }
      
      if (budgetRes?.ok) {
        const budgetData = await budgetRes.json()
        setBudget(budgetData.data)
      }
      
      if (profitabilityRes?.ok) {
        const profitabilityData = await profitabilityRes.json()
        setProfitability(profitabilityData.data)
      }
      
      if (forecastRes?.ok) {
        const forecastData = await forecastRes.json()
        setForecast(forecastData.data)
      }
    } catch (err) {
      console.error('Error fetching finance data:', err)
    } finally {
      setLoading(false)
    }
  }
  
  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-center">
          <Wallet className="w-12 h-12 text-aria-500 mx-auto animate-pulse" />
          <p className="mt-4 text-surface-400">Cargando métricas financieras...</p>
        </div>
      </div>
    )
  }
  
  const tabs = [
    { id: 'overview', label: 'Resumen', icon: BarChart3 },
    { id: 'ratios', label: 'Ratios', icon: Calculator },
    { id: 'budget', label: 'Presupuesto', icon: Target },
    { id: 'profitability', label: 'Rentabilidad', icon: TrendingUp },
    { id: 'forecast', label: 'Proyecciones', icon: PieChart },
  ]
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Wallet className="w-6 h-6 text-aria-500" />
            Planeación Financiera
          </h1>
          <p className="text-surface-500 text-sm mt-1">Análisis financiero profesional y métricas avanzadas</p>
        </div>
      </div>
      
      {/* Tabs */}
      <div className="flex gap-2 border-b border-surface-800">
        {tabs.map(tab => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 flex items-center gap-2 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-aria-500 text-aria-400'
                  : 'border-transparent text-surface-500 hover:text-surface-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>
      
      {/* Overview Tab */}
      {activeTab === 'overview' && summary && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Saldo Disponible"
              value={formatCurrency(summary.cash_balance)}
              subtitle={`Runway: ${Math.round(summary.runway_days || 0)} días`}
              icon={Wallet}
              status={summary.status}
            />
            <MetricCard
              title="Ingresos del Mes"
              value={formatCurrency(summary.monthly_revenue)}
              subtitle={`Presupuesto: ${summary.budget_compliance?.toFixed(1) || 0}%`}
              icon={DollarSign}
              status={summary.budget_compliance >= 80 ? 'ok' : 'warning'}
            />
            <MetricCard
              title="Pagos Próximos (7d)"
              value={formatCurrency(summary.upcoming_payments_7d)}
              subtitle={`Cobranza esperada: ${formatCurrency(summary.expected_collections_7d)}`}
              icon={AlertTriangle}
              status={summary.net_position_7d >= 0 ? 'ok' : 'warning'}
            />
            <MetricCard
              title="Posición Neta (7d)"
              value={formatCurrency(summary.net_position_7d)}
              subtitle={summary.net_position_7d >= 0 ? 'Fondos suficientes' : 'Faltante de fondos'}
              icon={CheckCircle2}
              status={summary.net_position_7d >= 0 ? 'ok' : 'critical'}
            />
          </div>
          
          {budget && <BudgetComparison data={budget} />}
        </div>
      )}
      
      {/* Ratios Tab */}
      {activeTab === 'ratios' && ratios && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <MetricCard
              title="Margen Neto"
              value={formatPercent(ratios.net_margin)}
              subtitle="Porcentaje de ganancia neta"
              icon={TrendingUp}
              status={ratios.net_margin >= 10 ? 'ok' : ratios.net_margin >= 5 ? 'warning' : 'critical'}
            />
            <MetricCard
              title="Ratio Gastos/Ingresos"
              value={formatPercent(ratios.expense_ratio)}
              subtitle="Porcentaje de gastos sobre ingresos"
              icon={Calculator}
              status={ratios.expense_ratio <= 70 ? 'ok' : ratios.expense_ratio <= 90 ? 'warning' : 'critical'}
            />
            <MetricCard
              title="Liquidez Corriente"
              value={ratios.current_ratio?.toFixed(2) || '-'}
              subtitle="Ratio de liquidez"
              icon={Wallet}
              status={ratios.current_ratio >= 1.0 ? 'ok' : 'critical'}
            />
            <MetricCard
              title="Crecimiento Ingresos"
              value={formatPercent(ratios.revenue_growth)}
              subtitle="Crecimiento mensual"
              icon={ratios.revenue_growth >= 0 ? TrendingUp : TrendingDown}
              trend={ratios.revenue_growth}
              status={ratios.revenue_growth >= 0 ? 'ok' : 'warning'}
            />
          </div>
          
          {ratios.months_data && (
            <SimpleBarChart
              title="Tendencias (últimos 3 meses)"
              data={ratios.months_data.map(m => ({
                label: m.month,
                value: m.net,
              }))}
            />
          )}
        </div>
      )}
      
      {/* Budget Tab */}
      {activeTab === 'budget' && budget && (
        <div className="space-y-6">
          <BudgetComparison data={budget} />
          
          {budget.projected_revenue && (
            <div className="glass rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-4">Proyección al Final del Mes</h3>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <p className="text-sm text-surface-400 mb-1">Ingresos Proyectados</p>
                  <p className="text-2xl font-bold font-mono">{formatCurrency(budget.projected_revenue)}</p>
                </div>
                <div>
                  <p className="text-sm text-surface-400 mb-1">Gastos Proyectados</p>
                  <p className="text-2xl font-bold font-mono">{formatCurrency(budget.projected_expenses)}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Profitability Tab */}
      {activeTab === 'profitability' && profitability && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <MetricCard
              title="Margen de Contribución"
              value={formatPercent(profitability.margin_pct)}
              subtitle={formatCurrency(profitability.contribution_margin)}
              icon={TrendingUp}
              status={profitability.margin_pct >= 20 ? 'ok' : 'warning'}
            />
            <MetricCard
              title="Punto de Equilibrio"
              value={formatCurrency(profitability.break_even)}
              subtitle="Ingresos necesarios para cubrir costos"
              icon={Target}
            />
            <MetricCard
              title="Gastos Totales"
              value={formatCurrency(profitability.total_expenses)}
              subtitle={`Ingresos: ${formatCurrency(profitability.total_revenue)}`}
              icon={Calculator}
            />
          </div>
          
          {profitability.expenses_by_category && (
            <SimpleBarChart
              title="Gastos por Categoría (Top 10)"
              data={Object.entries(profitability.expenses_by_category)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10)
                .map(([label, value]) => ({ label, value }))}
            />
          )}
          
          {profitability.revenue_by_product && Object.keys(profitability.revenue_by_product).length > 0 && (
            <SimpleBarChart
              title="Ingresos por Producto/Servicio (Top 5)"
              data={Object.entries(profitability.revenue_by_product)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5)
                .map(([label, value]) => ({ label, value }))}
            />
          )}
        </div>
      )}
      
      {/* Forecast Tab */}
      {activeTab === 'forecast' && forecast && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="glass rounded-xl p-6 border border-emerald-500/30 bg-emerald-500/10">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                Escenario Optimista
              </h3>
              <div className="space-y-2">
                <div>
                  <p className="text-sm text-surface-400">Ingresos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast.scenarios?.optimistic?.revenue)}</p>
                </div>
                <div>
                  <p className="text-sm text-surface-400">Gastos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast.scenarios?.optimistic?.expenses)}</p>
                </div>
                <div className="pt-2 border-t border-surface-800">
                  <p className="text-sm text-surface-400">Neto</p>
                  <p className="text-2xl font-bold font-mono text-emerald-400">{formatCurrency(forecast.scenarios?.optimistic?.net)}</p>
                </div>
              </div>
            </div>
            
            <div className="glass rounded-xl p-6 border border-amber-500/30 bg-amber-500/10">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Target className="w-5 h-5 text-amber-400" />
                Escenario Realista
              </h3>
              <div className="space-y-2">
                <div>
                  <p className="text-sm text-surface-400">Ingresos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast.scenarios?.realistic?.revenue)}</p>
                </div>
                <div>
                  <p className="text-sm text-surface-400">Gastos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast.scenarios?.realistic?.expenses)}</p>
                </div>
                <div className="pt-2 border-t border-surface-800">
                  <p className="text-sm text-surface-400">Neto</p>
                  <p className="text-2xl font-bold font-mono text-amber-400">{formatCurrency(forecast.scenarios?.realistic?.net)}</p>
                </div>
              </div>
            </div>
            
            <div className="glass rounded-xl p-6 border border-red-500/30 bg-red-500/10">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-red-400" />
                Escenario Pesimista
              </h3>
              <div className="space-y-2">
                <div>
                  <p className="text-sm text-surface-400">Ingresos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast.scenarios?.pessimistic?.revenue)}</p>
                </div>
                <div>
                  <p className="text-sm text-surface-400">Gastos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast.scenarios?.pessimistic?.expenses)}</p>
                </div>
                <div className="pt-2 border-t border-surface-800">
                  <p className="text-sm text-surface-400">Neto</p>
                  <p className="text-2xl font-bold font-mono text-red-400">{formatCurrency(forecast.scenarios?.pessimistic?.net)}</p>
                </div>
              </div>
            </div>
          </div>
          
          <div className="glass rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Promedio Histórico</h3>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <p className="text-sm text-surface-400 mb-1">Ingresos Mensuales Promedio</p>
                <p className="text-2xl font-bold font-mono">{formatCurrency(forecast.avg_monthly_revenue)}</p>
              </div>
              <div>
                <p className="text-sm text-surface-400 mb-1">Gastos Mensuales Promedio</p>
                <p className="text-2xl font-bold font-mono">{formatCurrency(forecast.avg_monthly_expenses)}</p>
              </div>
              <div className="col-span-2">
                <p className="text-sm text-surface-400 mb-1">Tasa de Crecimiento</p>
                <p className="text-xl font-bold font-mono">{formatPercent(forecast.growth_rate)}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
