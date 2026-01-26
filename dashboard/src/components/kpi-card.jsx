import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export function KPICard({ title, value, subtitle, icon: Icon, status, trend, onClick }) {
  const statusColors = {
    critical: "border-destructive/50 bg-destructive/10",
    warning: "border-yellow-500/50 bg-yellow-500/10",
    ok: "border-green-500/50 bg-green-500/10",
  }

  return (
    <Card
      className={cn(
        "cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98]",
        status && statusColors[status],
        onClick && "hover:shadow-lg"
      )}
      onClick={onClick}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
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
            <span>{trend >= 0 ? "↑" : "↓"}</span>
            <span className="ml-1">{Math.abs(trend).toFixed(1)}% vs periodo anterior</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
