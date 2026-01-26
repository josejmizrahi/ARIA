import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { TrendingUp, TrendingDown } from "lucide-react"
import { cn } from "@/lib/utils"

const STATUS_COLORS = {
  ok: "border-green-500/50 bg-green-500/10",
  warning: "border-yellow-500/50 bg-yellow-500/10",
  critical: "border-red-500/50 bg-red-500/10",
}

function formatPercent(value) {
  if (value === undefined || value === null) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

export function MetricCard({ title, value, subtitle, icon: Icon, trend, status }) {
  return (
    <Card className={cn(status && STATUS_COLORS[status])}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {subtitle && (
          <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
        )}
        {trend !== undefined && (
          <div className={cn(
            "flex items-center text-xs mt-2",
            trend >= 0 ? "text-green-500" : "text-red-500"
          )}>
            {trend >= 0 ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
            <span>{formatPercent(trend)}</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
