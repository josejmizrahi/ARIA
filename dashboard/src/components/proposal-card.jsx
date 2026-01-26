import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { CheckCircle2, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"

const PRIORITY_COLORS = {
  critical: "border-l-destructive",
  high: "border-l-yellow-500",
  medium: "border-l-blue-500",
  low: "border-l-muted",
}

export function ProposalCard({ proposal, onApprove, onReject }) {
  const priority = proposal.priority?.toLowerCase() || 'medium'
  
  return (
    <Card className={cn("border-l-4", PRIORITY_COLORS[priority])}>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="outline" className="text-xs">
                {proposal.agent_name}
              </Badge>
              <Badge 
                variant={priority === 'critical' ? 'destructive' : priority === 'high' ? 'secondary' : 'default'}
                className="text-xs capitalize"
              >
                {priority}
              </Badge>
            </div>
            <CardTitle className="text-base">{proposal.title}</CardTitle>
            <CardDescription className="mt-1 line-clamp-2">
              {proposal.description || proposal.situation_summary?.slice(0, 100)}
            </CardDescription>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-green-600 hover:text-green-700 hover:bg-green-500/10"
              onClick={(e) => {
                e.stopPropagation()
                onApprove(proposal.id)
              }}
            >
              <CheckCircle2 className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
              onClick={(e) => {
                e.stopPropagation()
                onReject(proposal.id)
              }}
            >
              <AlertTriangle className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
    </Card>
  )
}
