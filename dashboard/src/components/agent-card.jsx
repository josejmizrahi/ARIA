import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const STATUS_COLORS = {
  critical: "border-destructive/50 bg-destructive/10",
  warning: "border-yellow-500/50 bg-yellow-500/10",
  ok: "border-green-500/50 bg-green-500/10",
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

export function AgentCard({ name, data, onClick, icon: Icon }) {
  const status = data?.status || 'ok'
  
  return (
    <Card
      className={cn(
        "cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98]",
        STATUS_COLORS[status],
        onClick && "hover:shadow-lg"
      )}
      onClick={onClick}
    >
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {Icon && <Icon className="h-5 w-5" />}
            <CardTitle className="text-base font-semibold capitalize">{name}</CardTitle>
          </div>
          <Badge variant={status === 'ok' ? 'default' : status === 'warning' ? 'secondary' : 'destructive'}>
            {status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {data && (
          <div className="space-y-2 text-sm">
            {data.cash_balance !== undefined && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Saldo</span>
                <span className="font-mono">{formatCurrency(data.cash_balance)}</span>
              </div>
            )}
            {data.total_overdue !== undefined && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Vencido</span>
                <span className="font-mono text-destructive">{formatCurrency(data.total_overdue)}</span>
              </div>
            )}
            {data.active_employees !== undefined && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Empleados</span>
                <span className="font-mono">{data.active_employees}</span>
              </div>
            )}
            {data.total_products !== undefined && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Productos</span>
                <span className="font-mono">{formatNumber(data.total_products)}</span>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
