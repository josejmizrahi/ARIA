import { useState, useEffect } from 'react'
import { 
  MessageSquare, 
  Bot, 
  ArrowRight, 
  Clock,
  AlertCircle,
  CheckCircle2,
  Search,
  RefreshCw
} from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"

const API_BASE = '/api'

function formatDate(dateStr) {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('es-MX', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

function MessageBubble({ message, isFromCurrent }) {
  const priorityVariants = {
    low: 'default',
    medium: 'secondary',
    high: 'outline',
    critical: 'destructive',
  }
  
  return (
    <div className={`flex ${isFromCurrent ? 'justify-end' : 'justify-start'} mb-4`}>
      <Card className={`max-w-2xl ${isFromCurrent ? 'bg-primary/10' : ''}`}>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4" />
            <span className="font-semibold text-sm">{message.from_agent}</span>
            {message.to_agent && (
              <>
                <ArrowRight className="w-3 h-3 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">{message.to_agent}</span>
              </>
            )}
            <Badge variant={priorityVariants[message.priority] || 'default'} className="ml-auto text-xs">
              {message.priority}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {formatDate(message.created_at)}
            </span>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <CardTitle className="text-base mb-2">{message.subject}</CardTitle>
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          
          {message.data && Object.keys(message.data).length > 0 && (
            <div className="mt-3 pt-3 border-t">
              <details className="text-xs">
                <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                  Ver datos ({Object.keys(message.data).length} campos)
                </summary>
                <pre className="mt-2 p-2 bg-muted rounded text-xs overflow-x-auto">
                  {JSON.stringify(message.data, null, 2)}
                </pre>
              </details>
            </div>
          )}
          
          {message.requires_response && !message.responded_at && (
            <div className="mt-2 flex items-center gap-2 text-xs text-yellow-500">
              <Clock className="w-3 h-3" />
              Esperando respuesta
            </div>
          )}
          
          {message.responded_at && (
            <div className="mt-2 flex items-center gap-2 text-xs text-green-500">
              <CheckCircle2 className="w-3 h-3" />
              Respondido {formatDate(message.responded_at)}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function ConversationThread({ conversation }) {
  return (
    <Card className="mb-6">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>{conversation.subject}</CardTitle>
            <CardDescription>
              {conversation.from_agent} → {conversation.to_agent || 'Todos'}
            </CardDescription>
          </div>
          <Badge variant="outline">
            {conversation.message_count} mensajes
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {conversation.messages.map((msg, idx) => (
            <MessageBubble
              key={idx}
              message={msg}
              isFromCurrent={idx % 2 === 0}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export default function AgentConversations() {
  const [conversations, setConversations] = useState([])
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterAgent, setFilterAgent] = useState('')
  const [selectedConversation, setSelectedConversation] = useState(null)
  
  const fetchData = async () => {
    try {
      const [conversationsRes, messagesRes] = await Promise.all([
        fetch(`${API_BASE}/agents/conversations?limit=50`),
        fetch(`${API_BASE}/agents/messages?limit=100`),
      ])
      
      if (conversationsRes.ok) {
        const data = await conversationsRes.json()
        setConversations(data.conversations || [])
      }
      
      if (messagesRes.ok) {
        const data = await messagesRes.json()
        setMessages(data.messages || [])
      }
    } catch (err) {
      console.error('Error fetching conversations:', err)
    } finally {
      setLoading(false)
    }
  }
  
  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])
  
  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Card className="w-96">
          <CardContent className="pt-6">
            <div className="text-center">
              <MessageSquare className="w-12 h-12 text-primary mx-auto animate-pulse" />
              <p className="mt-4 text-muted-foreground">Cargando conversaciones...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }
  
  const filteredConversations = filterAgent
    ? conversations.filter(c => 
        c.from_agent.toLowerCase().includes(filterAgent.toLowerCase()) ||
        (c.to_agent && c.to_agent.toLowerCase().includes(filterAgent.toLowerCase()))
      )
    : conversations
  
  const filteredMessages = filterAgent
    ? messages.filter(m => 
        m.from_agent.toLowerCase().includes(filterAgent.toLowerCase()) ||
        (m.to_agent && m.to_agent.toLowerCase().includes(filterAgent.toLowerCase()))
      )
    : messages
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <MessageSquare className="w-6 h-6" />
            Conversaciones entre Agentes
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Cómo los agentes se comunican y colaboran para resolver problemas
          </p>
        </div>
        <Button variant="outline" onClick={fetchData}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Actualizar
        </Button>
      </div>
      
      {/* Filter */}
      <div className="flex items-center gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="text"
            value={filterAgent}
            onChange={(e) => setFilterAgent(e.target.value)}
            placeholder="Filtrar por agente..."
            className="pl-10"
          />
        </div>
      </div>
      
      {/* Tabs */}
      <Tabs defaultValue="conversations" className="space-y-4">
        <TabsList>
          <TabsTrigger value="conversations">
            Conversaciones ({conversations.length})
          </TabsTrigger>
          <TabsTrigger value="messages">
            Todos los Mensajes ({messages.length})
          </TabsTrigger>
        </TabsList>
        
        {/* Conversations Tab */}
        <TabsContent value="conversations">
          {selectedConversation ? (
            <div>
              <Button
                variant="ghost"
                onClick={() => setSelectedConversation(null)}
                className="mb-4"
              >
                ← Volver a conversaciones
              </Button>
              <ConversationThread conversation={selectedConversation} />
            </div>
          ) : (
            <div>
              {filteredConversations.length > 0 ? (
                filteredConversations.map((conv) => (
                  <Card
                    key={conv.id}
                    className="mb-4 cursor-pointer hover:bg-accent transition-colors"
                    onClick={() => setSelectedConversation(conv)}
                  >
                    <CardContent className="pt-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle className="text-base">{conv.subject}</CardTitle>
                          <CardDescription>
                            {conv.from_agent} → {conv.to_agent || 'Todos'} • {conv.message_count} mensajes
                          </CardDescription>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(conv.last_message)}
                        </span>
                      </div>
                    </CardContent>
                  </Card>
                ))
              ) : (
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-center py-8">
                      <MessageSquare className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
                      <p className="text-muted-foreground">No hay conversaciones aún</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        Los agentes comenzarán a comunicarse cuando detecten problemas
                      </p>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </TabsContent>
        
        {/* Messages Tab */}
        <TabsContent value="messages">
          <div className="space-y-4">
            {filteredMessages.length > 0 ? (
              filteredMessages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  isFromCurrent={false}
                />
              ))
            ) : (
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center py-8">
                    <MessageSquare className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
                    <p className="text-muted-foreground">No hay mensajes</p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
