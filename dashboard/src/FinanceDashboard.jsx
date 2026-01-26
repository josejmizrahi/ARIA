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
  Calculator,
  Settings,
  Save,
  X
} from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { MetricCard } from "@/components/metric-card"
import { SimpleBarChart } from "@/components/simple-bar-chart"

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

function BudgetComparison({ data }) {
  if (!data) return null
  
  const { actual_revenue, expected_revenue, revenue_variance_pct, actual_expenses, expected_expenses, expense_variance_pct } = data
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="w-5 h-5" />
          Comparativo vs Presupuesto
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="flex justify-between mb-2">
            <span className="text-sm text-muted-foreground">Ingresos</span>
            <Badge variant={revenue_variance_pct >= 0 ? 'default' : 'destructive'}>
              {formatPercent(revenue_variance_pct)}
            </Badge>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <p className="text-muted-foreground">Real</p>
              <p className="font-mono font-semibold">{formatCurrency(actual_revenue)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Esperado</p>
              <p className="font-mono font-semibold">{formatCurrency(expected_revenue)}</p>
            </div>
          </div>
        </div>
        
        <Separator />
        
        <div>
          <div className="flex justify-between mb-2">
            <span className="text-sm text-muted-foreground">Gastos</span>
            <Badge variant={expense_variance_pct <= 0 ? 'default' : 'destructive'}>
              {formatPercent(expense_variance_pct)}
            </Badge>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <p className="text-muted-foreground">Real</p>
              <p className="font-mono font-semibold">{formatCurrency(actual_expenses)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Esperado</p>
              <p className="font-mono font-semibold">{formatCurrency(expected_expenses)}</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function BudgetConfig({ budgets, onSave, onCancel }) {
  const [monthlyRevenue, setMonthlyRevenue] = useState(budgets?.monthly_revenue || 0)
  const [monthlyExpenses, setMonthlyExpenses] = useState(budgets?.monthly_expenses || 0)
  const [categories, setCategories] = useState(budgets?.by_category || {})
  const [newCategory, setNewCategory] = useState({ name: '', amount: '' })
  const [saving, setSaving] = useState(false)
  
  const handleAddCategory = () => {
    if (newCategory.name && newCategory.amount) {
      setCategories({
        ...categories,
        [newCategory.name]: parseFloat(newCategory.amount)
      })
      setNewCategory({ name: '', amount: '' })
    }
  }
  
  const handleRemoveCategory = (name) => {
    const updated = { ...categories }
    delete updated[name]
    setCategories(updated)
  }
  
  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave({
        monthly_revenue: monthlyRevenue,
        monthly_expenses: monthlyExpenses,
        by_category: categories
      })
    } finally {
      setSaving(false)
    }
  }
  
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Configurar Presupuestos
          </CardTitle>
          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={saving}>
              <Save className="w-4 h-4 mr-2" />
              {saving ? 'Guardando...' : 'Guardar'}
            </Button>
            <Button variant="outline" onClick={onCancel}>
              <X className="w-4 h-4 mr-2" />
              Cancelar
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Presupuesto Mensual de Ingresos</Label>
            <Input
              type="number"
              value={monthlyRevenue}
              onChange={(e) => setMonthlyRevenue(parseFloat(e.target.value) || 0)}
              placeholder="0"
              className="font-mono"
            />
          </div>
          
          <div className="space-y-2">
            <Label>Presupuesto Mensual de Gastos</Label>
            <Input
              type="number"
              value={monthlyExpenses}
              onChange={(e) => setMonthlyExpenses(parseFloat(e.target.value) || 0)}
              placeholder="0"
              className="font-mono"
            />
          </div>
        </div>
        
        <div className="space-y-2">
          <Label>Presupuestos por Categoría</Label>
          
          <div className="space-y-2 mb-4">
            {Object.entries(categories).map(([name, amount]) => (
              <Card key={name}>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2">
                    <span className="flex-1 font-medium">{name}</span>
                    <span className="font-mono">{formatCurrency(amount)}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleRemoveCategory(name)}
                    >
                      <X className="w-4 h-4 text-destructive" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
          
          <div className="flex gap-2">
            <Input
              type="text"
              value={newCategory.name}
              onChange={(e) => setNewCategory({ ...newCategory, name: e.target.value })}
              placeholder="Nombre de categoría"
              className="flex-1"
            />
            <Input
              type="number"
              value={newCategory.amount}
              onChange={(e) => setNewCategory({ ...newCategory, amount: e.target.value })}
              placeholder="Monto"
              className="w-32 font-mono"
            />
            <Button onClick={handleAddCategory}>
              Agregar
            </Button>
          </div>
        </div>
        
        {budgets?.source && (
          <div className="pt-4 border-t">
            <p className="text-sm text-muted-foreground">
              Fuente actual: <span className="font-medium capitalize">{budgets.source}</span>
              {budgets.source === 'odoo' && budgets.name && (
                <span className="ml-2">({budgets.name})</span>
              )}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function FinanceDashboard() {
  const [summary, setSummary] = useState(null)
  const [ratios, setRatios] = useState(null)
  const [budget, setBudget] = useState(null)
  const [profitability, setProfitability] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [budgets, setBudgets] = useState(null)
  const [bankAccounts, setBankAccounts] = useState(null)
  const [companies, setCompanies] = useState([])
  const [selectedCompany, setSelectedCompany] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showBudgetConfig, setShowBudgetConfig] = useState(false)
  
  useEffect(() => {
    fetchFinanceData()
    const interval = setInterval(fetchFinanceData, 60000)
    return () => clearInterval(interval)
  }, [selectedCompany])
  
  useEffect(() => {
    fetch(`${API_BASE}/companies`)
      .then(res => res.json())
      .then(data => {
        setCompanies(data.companies || [])
        if (data.companies && data.companies.length > 0 && !selectedCompany) {
          // Buscar company_id = 1 primero, si no existe usar la primera disponible
          const companyId1 = data.companies.find(c => c.id === 1)
          setSelectedCompany(companyId1 ? 1 : data.companies[0].id)
        }
      })
      .catch(err => console.error('Error cargando compañías:', err))
  }, [])
  
  const fetchFinanceData = async () => {
    try {
      const [summaryRes, ratiosRes, budgetRes, profitabilityRes, forecastRes, budgetsRes, bankAccountsRes] = await Promise.all([
        fetch(`${API_BASE}/agents/finanzas/summary`),
        fetch(`${API_BASE}/finance/ratios`).catch(() => null),
        fetch(`${API_BASE}/finance/budget`).catch(() => null),
        fetch(`${API_BASE}/finance/profitability`).catch(() => null),
        fetch(`${API_BASE}/finance/forecast`).catch(() => null),
        fetch(`${API_BASE}/finance/budgets`).catch(() => null),
        fetch(`${API_BASE}/finance/bank-accounts`).catch(() => null),
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
      
      if (budgetsRes?.ok) {
        const budgetsData = await budgetsRes.json()
        setBudgets(budgetsData.budgets)
      }
      
      if (bankAccountsRes?.ok) {
        const bankAccountsData = await bankAccountsRes.json()
        setBankAccounts(bankAccountsData)
      }
    } catch (err) {
      console.error('Error fetching finance data:', err)
    } finally {
      setLoading(false)
    }
  }
  
  const handleSaveBudgets = async (budgetData) => {
    try {
      const response = await fetch(`${API_BASE}/finance/budgets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(budgetData)
      })
      
      if (response.ok) {
        const result = await response.json()
        setBudgets(result.budgets)
        setShowBudgetConfig(false)
        fetchFinanceData()
      } else {
        alert('Error guardando presupuestos')
      }
    } catch (err) {
      console.error('Error saving budgets:', err)
      alert('Error guardando presupuestos')
    }
  }
  
  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Card className="w-96">
          <CardContent className="pt-6">
            <div className="text-center">
              <Wallet className="w-12 h-12 text-primary mx-auto animate-pulse" />
              <p className="mt-4 text-muted-foreground">Cargando métricas financieras...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Wallet className="w-6 h-6" />
            Planeación Financiera
          </h1>
          <p className="text-muted-foreground text-sm mt-1">Análisis financiero profesional y métricas avanzadas</p>
        </div>
        <div className="flex items-center gap-3">
          {companies.length > 1 && (
            <Select value={selectedCompany?.toString()} onValueChange={(v) => setSelectedCompany(parseInt(v))}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Seleccionar empresa" />
              </SelectTrigger>
              <SelectContent>
                {companies.map(comp => (
                  <SelectItem key={comp.id} value={comp.id.toString()}>
                    {comp.name} ({comp.currency})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Button variant="outline" onClick={() => setShowBudgetConfig(!showBudgetConfig)}>
            <Settings className="w-4 h-4 mr-2" />
            {showBudgetConfig ? 'Ocultar Configuración' : 'Configurar Presupuestos'}
          </Button>
        </div>
      </div>
      
      {/* Budget Configuration */}
      {showBudgetConfig && budgets && (
        <BudgetConfig
          budgets={budgets}
          onSave={handleSaveBudgets}
          onCancel={() => setShowBudgetConfig(false)}
        />
      )}
      
      {/* Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">
            <BarChart3 className="w-4 h-4 mr-2" />
            Resumen
          </TabsTrigger>
          <TabsTrigger value="ratios">
            <Calculator className="w-4 h-4 mr-2" />
            Ratios
          </TabsTrigger>
          <TabsTrigger value="budget">
            <Target className="w-4 h-4 mr-2" />
            Presupuesto
          </TabsTrigger>
          <TabsTrigger value="profitability">
            <TrendingUp className="w-4 h-4 mr-2" />
            Rentabilidad
          </TabsTrigger>
          <TabsTrigger value="forecast">
            <PieChart className="w-4 h-4 mr-2" />
            Proyecciones
          </TabsTrigger>
        </TabsList>
        
        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Saldos por Divisa */}
          {summary?.cash_by_currency && Object.keys(summary.cash_by_currency).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Wallet className="w-5 h-5" />
                  Saldos por Divisa
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {Object.entries(summary.cash_by_currency).map(([currency, balance]) => (
                    <Card key={currency}>
                      <CardContent className="pt-4">
                        <p className="text-sm text-muted-foreground mb-1">{currency}</p>
                        <p className="text-2xl font-bold font-mono">{formatCurrency(balance)}</p>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
          
          {/* Saldos por Cuenta Bancaria */}
          {bankAccounts?.accounts_by_currency && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Wallet className="w-5 h-5" />
                  Saldos por Cuenta Bancaria
                </CardTitle>
              </CardHeader>
              <CardContent>
                {Object.entries(bankAccounts.accounts_by_currency).map(([currency, accounts]) => (
                  <div key={currency} className="mb-6">
                    <h4 className="text-sm font-medium text-muted-foreground mb-3">{currency}</h4>
                    <div className="space-y-2">
                      {accounts.map((acc, idx) => (
                        <Card key={idx}>
                          <CardContent className="pt-4">
                            <div className="flex items-center justify-between">
                              <span className="font-medium">{acc.name}</span>
                              <span className="font-mono">{formatCurrency(acc.balance)}</span>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Saldo Disponible"
              value={formatCurrency(summary?.cash_balance)}
              subtitle={`Runway: ${Math.round(summary?.runway_days || 0)} días`}
              icon={Wallet}
              status={summary?.status}
            />
            <MetricCard
              title="Ingresos del Mes"
              value={formatCurrency(summary?.monthly_revenue)}
              subtitle={`Presupuesto: ${summary?.budget_compliance?.toFixed(1) || 0}%`}
              icon={DollarSign}
              status={summary?.budget_compliance >= 80 ? 'ok' : 'warning'}
            />
            <MetricCard
              title="Pagos Próximos (7d)"
              value={formatCurrency(summary?.upcoming_payments_7d)}
              subtitle={`Cobranza esperada: ${formatCurrency(summary?.expected_collections_7d)}`}
              icon={AlertTriangle}
              status={summary?.net_position_7d >= 0 ? 'ok' : 'warning'}
            />
            <MetricCard
              title="Posición Neta (7d)"
              value={formatCurrency(summary?.net_position_7d)}
              subtitle={summary?.net_position_7d >= 0 ? 'Fondos suficientes' : 'Faltante de fondos'}
              icon={CheckCircle2}
              status={summary?.net_position_7d >= 0 ? 'ok' : 'critical'}
            />
          </div>
          
          {budget && <BudgetComparison data={budget} />}
        </TabsContent>
        
        {/* Ratios Tab */}
        <TabsContent value="ratios" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-4">
              <MetricCard
                title="Margen Neto"
                value={formatPercent(ratios?.net_margin)}
                subtitle="Porcentaje de ganancia neta"
                icon={TrendingUp}
                status={ratios?.net_margin >= 10 ? 'ok' : ratios?.net_margin >= 5 ? 'warning' : 'critical'}
              />
              <MetricCard
                title="Ratio Gastos/Ingresos"
                value={formatPercent(ratios?.expense_ratio)}
                subtitle="Porcentaje de gastos sobre ingresos"
                icon={Calculator}
                status={ratios?.expense_ratio <= 70 ? 'ok' : ratios?.expense_ratio <= 90 ? 'warning' : 'critical'}
              />
              <MetricCard
                title="Liquidez Corriente"
                value={ratios?.current_ratio?.toFixed(2) || '-'}
                subtitle="Ratio de liquidez"
                icon={Wallet}
                status={ratios?.current_ratio >= 1.0 ? 'ok' : 'critical'}
              />
              <MetricCard
                title="Crecimiento Ingresos"
                value={formatPercent(ratios?.revenue_growth)}
                subtitle="Crecimiento mensual"
                icon={ratios?.revenue_growth >= 0 ? TrendingUp : TrendingDown}
                trend={ratios?.revenue_growth}
                status={ratios?.revenue_growth >= 0 ? 'ok' : 'warning'}
              />
            </div>
            
            {ratios?.months_data && (
              <SimpleBarChart
                title="Tendencias (últimos 3 meses)"
                data={ratios.months_data.map(m => ({
                  label: m.month,
                  value: m.net,
                }))}
              />
            )}
          </div>
        </TabsContent>
        
        {/* Budget Tab */}
        <TabsContent value="budget" className="space-y-6">
          {budgets && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Presupuestos Configurados</CardTitle>
                  <Badge variant={budgets.source === 'odoo' ? 'default' : budgets.source === 'manual' ? 'secondary' : 'outline'}>
                    Fuente: {budgets.source === 'odoo' ? 'Odoo' : budgets.source === 'manual' ? 'Manual' : 'Calculado'}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Ingresos Mensuales</p>
                    <p className="text-xl font-bold font-mono">{formatCurrency(budgets.monthly_revenue)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Gastos Mensuales</p>
                    <p className="text-xl font-bold font-mono">{formatCurrency(budgets.monthly_expenses)}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
          
          {budget && <BudgetComparison data={budget} />}
          
          {budget?.projected_revenue && (
            <Card>
              <CardHeader>
                <CardTitle>Proyección al Final del Mes</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Ingresos Proyectados</p>
                    <p className="text-2xl font-bold font-mono">{formatCurrency(budget.projected_revenue)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Gastos Proyectados</p>
                    <p className="text-2xl font-bold font-mono">{formatCurrency(budget.projected_expenses)}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
        
        {/* Profitability Tab */}
        <TabsContent value="profitability" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <MetricCard
              title="Margen de Contribución"
              value={formatPercent(profitability?.margin_pct)}
              subtitle={formatCurrency(profitability?.contribution_margin)}
              icon={TrendingUp}
              status={profitability?.margin_pct >= 20 ? 'ok' : 'warning'}
            />
            <MetricCard
              title="Punto de Equilibrio"
              value={formatCurrency(profitability?.break_even)}
              subtitle="Ingresos necesarios para cubrir costos"
              icon={Target}
            />
            <MetricCard
              title="Gastos Totales"
              value={formatCurrency(profitability?.total_expenses)}
              subtitle={`Ingresos: ${formatCurrency(profitability?.total_revenue)}`}
              icon={Calculator}
            />
          </div>
          
          {profitability?.expenses_by_category && (
            <SimpleBarChart
              title="Gastos por Categoría (Top 10)"
              data={Object.entries(profitability.expenses_by_category)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10)
                .map(([label, value]) => ({ label, value }))}
            />
          )}
          
          {profitability?.revenue_by_product && Object.keys(profitability.revenue_by_product).length > 0 && (
            <SimpleBarChart
              title="Ingresos por Producto/Servicio (Top 5)"
              data={Object.entries(profitability.revenue_by_product)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5)
                .map(([label, value]) => ({ label, value }))}
            />
          )}
        </TabsContent>
        
        {/* Forecast Tab */}
        <TabsContent value="forecast" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="border-green-500/50 bg-green-500/10">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-green-500" />
                  Escenario Optimista
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div>
                  <p className="text-sm text-muted-foreground">Ingresos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast?.scenarios?.optimistic?.revenue)}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Gastos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast?.scenarios?.optimistic?.expenses)}</p>
                </div>
                <Separator />
                <div>
                  <p className="text-sm text-muted-foreground">Neto</p>
                  <p className="text-2xl font-bold font-mono text-green-500">{formatCurrency(forecast?.scenarios?.optimistic?.net)}</p>
                </div>
              </CardContent>
            </Card>
            
            <Card className="border-yellow-500/50 bg-yellow-500/10">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="w-5 h-5 text-yellow-500" />
                  Escenario Realista
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div>
                  <p className="text-sm text-muted-foreground">Ingresos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast?.scenarios?.realistic?.revenue)}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Gastos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast?.scenarios?.realistic?.expenses)}</p>
                </div>
                <Separator />
                <div>
                  <p className="text-sm text-muted-foreground">Neto</p>
                  <p className="text-2xl font-bold font-mono text-yellow-500">{formatCurrency(forecast?.scenarios?.realistic?.net)}</p>
                </div>
              </CardContent>
            </Card>
            
            <Card className="border-red-500/50 bg-red-500/10">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-500" />
                  Escenario Pesimista
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div>
                  <p className="text-sm text-muted-foreground">Ingresos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast?.scenarios?.pessimistic?.revenue)}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Gastos</p>
                  <p className="text-xl font-bold font-mono">{formatCurrency(forecast?.scenarios?.pessimistic?.expenses)}</p>
                </div>
                <Separator />
                <div>
                  <p className="text-sm text-muted-foreground">Neto</p>
                  <p className="text-2xl font-bold font-mono text-red-500">{formatCurrency(forecast?.scenarios?.pessimistic?.net)}</p>
                </div>
              </CardContent>
            </Card>
          </div>
          
          <Card>
            <CardHeader>
              <CardTitle>Promedio Histórico</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Ingresos Mensuales Promedio</p>
                  <p className="text-2xl font-bold font-mono">{formatCurrency(forecast?.avg_monthly_revenue)}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Gastos Mensuales Promedio</p>
                  <p className="text-2xl font-bold font-mono">{formatCurrency(forecast?.avg_monthly_expenses)}</p>
                </div>
                <div className="col-span-2">
                  <p className="text-sm text-muted-foreground mb-1">Tasa de Crecimiento</p>
                  <p className="text-xl font-bold font-mono">{formatPercent(forecast?.growth_rate)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
