import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

function formatCurrency(value) {
  if (value === undefined || value === null) return '-'
  return new Intl.NumberFormat('es-MX', { 
    style: 'currency', 
    currency: 'MXN',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

export function SimpleBarChart({ data, title }) {
  if (!data || data.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-center text-muted-foreground">No hay datos disponibles</p>
        </CardContent>
      </Card>
    )
  }
  
  const maxValue = Math.max(...data.map(d => d.value))
  
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {data.map((item, i) => (
            <div key={i}>
              <div className="flex justify-between mb-1">
                <span className="text-sm text-muted-foreground truncate">{item.label}</span>
                <span className="text-sm font-mono">{formatCurrency(item.value)}</span>
              </div>
              <div className="h-2 bg-secondary rounded-full overflow-hidden">
                <div 
                  className="h-full bg-primary rounded-full transition-all"
                  style={{ width: `${(item.value / maxValue) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
