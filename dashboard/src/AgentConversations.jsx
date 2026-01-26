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
  const priorityColors = {
    low: 'bg-surface-800',
    medium: 'bg-blue-500/20 border-blue-500/30',
    high: 'bg-amber-500/20 border-amber-500/30',
    critical: 'bg-red-500/20 border-red-500/30',
  }
  
  return (
    <div className={`flex ${isFromCurrent ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-2xl rounded-xl p-4 border ${priorityColors[message.priority] || 'bg-surface-800'}`}>
        <div className="flex items-center gap-2 mb-2">
          <Bot className="w-4 h-4" />
          <span className="font-semibold text-sm">{message.from_agent}</span>
          {message.to_agent && (
            <>
              <ArrowRight className="w-3 h-3 text-surface-500" />
              <span className="text-sm text-surface-400">{message.to_agent}</span>
            </>
          )}
          <span className="ml-auto text-xs text-surface-500">
            {formatDate(message.created_at)}
          </span>
        </div>
        
        <h4 className="font-medium mb-2">{message.subject}</h4>
        <p className="text-sm text-surface-300 whitespace-pre-wrap">{message.content}</p>
        
        {message.data && Object.keys(message.data).length > 0 && (
          <div className="mt-3 pt-3 border-t border-surface-800">
            <details className="text-xs">
              <summary className="cursor-pointer text-surface-400 hover:text-surface-300">
                Ver datos ({Object.keys(message.data).length} campos)
              </summary>
              <pre className="mt-2 p-2 bg-surface-950 rounded text-xs overflow-x-auto">
                {JSON.stringify(message.data, null, 2)}
              </pre>
            </details>
          </div>
        )}
        
        {message.requires_response && !message.responded_at && (
          <div className="mt-2 flex items-center gap-2 text-xs text-amber-400">
            <Clock className="w-3 h-3" />
            Esperando respuesta
          </div>
        )}
        
        {message.responded_at && (
          <div className="mt-2 flex items-center gap-2 text-xs text-emerald-400">
            <CheckCircle2 className="w-3 h-3" />
            Respondido {formatDate(message.responded_at)}
          </div>
        )}
      </div>
    </div>
  )
}

function ConversationThread({ conversation }) {
  return (
    <div className="glass rounded-xl p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold">{conversation.subject}</h3>
          <p className="text-sm text-surface-400">
            {conversation.from_agent} → {conversation.to_agent || 'Todos'}
          </p>
        </div>
        <span className="text-xs text-surface-500">
          {conversation.message_count} mensajes
        </span>
      </div>
      
      <div className="space-y-2">
        {conversation.messages.map((msg, idx) => (
          <MessageBubble
            key={idx}
            message={msg}
            isFromCurrent={idx % 2 === 0}
          />
        ))}
      </div>
    </div>
  )
}

export default function AgentConversations() {
  const [conversations, setConversations] = useState([])
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('conversations')
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
    const interval = setInterval(fetchData, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])
  
  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-center">
          <MessageSquare className="w-12 h-12 text-aria-500 mx-auto animate-pulse" />
          <p className="mt-4 text-surface-400">Cargando conversaciones...</p>
        </div>
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
            <MessageSquare className="w-6 h-6 text-aria-500" />
            Conversaciones entre Agentes
          </h1>
          <p className="text-surface-500 text-sm mt-1">
            Cómo los agentes se comunican y colaboran para resolver problemas
          </p>
        </div>
        <button
          onClick={fetchData}
          className="px-4 py-2 bg-surface-800 hover:bg-surface-700 rounded-lg flex items-center gap-2 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Actualizar
        </button>
      </div>
      
      {/* Filter */}
      <div className="flex items-center gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-surface-500" />
          <input
            type="text"
            value={filterAgent}
            onChange={(e) => setFilterAgent(e.target.value)}
            placeholder="Filtrar por agente..."
            className="w-full pl-10 pr-4 py-2 bg-surface-900 border border-surface-800 rounded-lg"
          />
        </div>
      </div>
      
      {/* Tabs */}
      <div className="flex gap-2 border-b border-surface-800">
        <button
          onClick={() => setActiveTab('conversations')}
          className={`px-4 py-2 border-b-2 transition-colors ${
            activeTab === 'conversations'
              ? 'border-aria-500 text-aria-400'
              : 'border-transparent text-surface-500 hover:text-surface-300'
          }`}
        >
          Conversaciones ({conversations.length})
        </button>
        <button
          onClick={() => setActiveTab('messages')}
          className={`px-4 py-2 border-b-2 transition-colors ${
            activeTab === 'messages'
              ? 'border-aria-500 text-aria-400'
              : 'border-transparent text-surface-500 hover:text-surface-300'
          }`}
        >
          Todos los Mensajes ({messages.length})
        </button>
      </div>
      
      {/* Content */}
      {activeTab === 'conversations' && (
        <div>
          {selectedConversation ? (
            <div>
              <button
                onClick={() => setSelectedConversation(null)}
                className="mb-4 text-sm text-surface-400 hover:text-surface-300"
              >
                ← Volver a conversaciones
              </button>
              <ConversationThread conversation={selectedConversation} />
            </div>
          ) : (
            <div>
              {filteredConversations.length > 0 ? (
                filteredConversations.map((conv) => (
                  <div
                    key={conv.id}
                    onClick={() => setSelectedConversation(conv)}
                    className="glass rounded-xl p-4 mb-4 cursor-pointer hover:bg-surface-800/50 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-semibold">{conv.subject}</h3>
                        <p className="text-sm text-surface-400">
                          {conv.from_agent} → {conv.to_agent || 'Todos'} • {conv.message_count} mensajes
                        </p>
                      </div>
                      <span className="text-xs text-surface-500">
                        {formatDate(conv.last_message)}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="glass rounded-xl p-8 text-center">
                  <MessageSquare className="w-12 h-12 text-surface-600 mx-auto mb-3" />
                  <p className="text-surface-400">No hay conversaciones aún</p>
                  <p className="text-sm text-surface-500 mt-1">
                    Los agentes comenzarán a comunicarse cuando detecten problemas
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      {activeTab === 'messages' && (
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
            <div className="glass rounded-xl p-8 text-center">
              <MessageSquare className="w-12 h-12 text-surface-600 mx-auto mb-3" />
              <p className="text-surface-400">No hay mensajes</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
