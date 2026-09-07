import { useAuth } from '@/auth/AuthContext';
import { useState, useRef, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Link } from 'react-router-dom';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Send, Bot, User, MessageSquare, ChevronDown, ChevronUp,
  Code2, Bed, Bath, MapPin, Ruler, Home, Building2,
} from 'lucide-react';
import { chatApi } from '@/services/api';
import type { ChatResponse, PropertyResult } from '@/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
  response?: ChatResponse;
}

// ---------------------------------------------------------------------------
// Property Card
// ---------------------------------------------------------------------------
function ChatPropertyCard({ property }: { property: PropertyResult }) {
  const isRent = property.intent === 'rent';
  const currency = property.currency || 'USD';
  const formattedPrice = new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(property.price);
  const isApartment = property.property_type === 'apartment';
  const imgSrc = isApartment
    ? `/images/apartments/apartment_0${(property.id % 4) + 1}.webp`
    : `/images/houses/house_0${(property.id % 4) + 1}.webp`;

  return (
    <Card className="flex gap-3 p-3 border rounded-xl overflow-hidden hover:shadow-md transition-shadow bg-background">
      <Link to={property.property_url} className="contents" aria-label={`View ${property.title}`}>
      <img
        src={imgSrc}
        alt={property.title}
        className="w-20 h-20 object-cover rounded-lg shrink-0"
        onError={(e) => { (e.target as HTMLImageElement).src = '/images/apartments/apartment.jpg'; }}
      />
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm truncate">{property.title}</p>
        <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
          <MapPin className="h-3 w-3" />
          <span>{property.neighbourhood}, {property.city}</span>
        </div>
        <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><Bed className="h-3 w-3" />{property.bedrooms}</span>
          <span className="flex items-center gap-1"><Bath className="h-3 w-3" />{property.bathrooms}</span>
          <span className="flex items-center gap-1"><Ruler className="h-3 w-3" />{property.size_sqm}m²</span>
          <span className="flex items-center gap-1">
            {isApartment ? <Building2 className="h-3 w-3" /> : <Home className="h-3 w-3" />}
            {property.property_type}
          </span>
        </div>
        <div className="flex items-center justify-between mt-1.5">
          <span className="font-bold text-sm text-accent">
            {formattedPrice}{isRent ? '/mo' : ''}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            isRent ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
          }`}>
            {property.intent}
          </span>
        </div>
      </div>
      </Link>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// SQL Debug Panel
// ---------------------------------------------------------------------------
function SqlDebugPanel({ sql, intent }: { sql?: string; intent?: string }) {
  const IS_DEV_MODE = false;
  const [open, setOpen] = useState(false);
  if (!sql || !IS_DEV_MODE) return null;
  return (
    <div className="mt-2 border rounded-lg overflow-hidden text-xs">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 bg-muted/40 hover:bg-muted/70 transition-colors font-mono"
      >
        <span className="flex items-center gap-2">
          <Code2 className="h-3 w-3" />
          SQL Debug
          {intent && <span className="ml-1 px-1.5 py-0.5 rounded bg-accent/20 text-accent">{intent}</span>}
        </span>
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {open && (
        <pre className="p-3 bg-muted/20 overflow-x-auto text-[11px] leading-relaxed text-muted-foreground whitespace-pre-wrap">
          {sql}
        </pre>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Message Bubble
// ---------------------------------------------------------------------------
function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';
  const resp = msg.response;

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${
        isUser ? 'bg-primary text-primary-foreground' : 'bg-accent text-accent-foreground'
      }`}>
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div className={`max-w-[80%] space-y-2 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? 'bg-primary text-primary-foreground rounded-tr-none'
            : 'bg-secondary text-secondary-foreground rounded-tl-none'
        }`}>
          {msg.content}
        </div>

        {/* Property cards */}
        {resp && resp.properties.length > 0 && (
          <div className="w-full space-y-2">
            <p className="text-xs text-muted-foreground px-1">
              {resp.result_count} result{resp.result_count !== 1 ? 's' : ''}
            </p>
            {resp.properties.slice(0, 5).map(p => (
              <ChatPropertyCard key={p.id} property={p} />
            ))}
            {resp.fallback_applied && resp.fallback_message && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">{resp.fallback_message}</p>
            )}
            {resp.result_count > 5 && (
              <div className="flex items-center justify-between text-xs px-1">
                <span className="text-muted-foreground">+ {resp.result_count - 5} more results</span>
                {resp.more_results_url && <Link to={resp.more_results_url} className="font-medium text-accent hover:underline">View all</Link>}
              </div>
            )}
          </div>
        )}

        {/* SQL debug panel */}
        {resp && <SqlDebugPanel sql={resp.generated_sql} intent={resp.intent} />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Typing indicator
// ---------------------------------------------------------------------------
function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="w-9 h-9 rounded-full bg-accent text-accent-foreground flex items-center justify-center shrink-0">
        <Bot className="h-4 w-4" />
      </div>
      <div className="px-4 py-4 rounded-2xl bg-secondary rounded-tl-none flex gap-1 items-center">
        {[0, 150, 300].map(delay => (
          <div
            key={delay}
            className="w-2 h-2 rounded-full bg-foreground/40 animate-bounce"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
const SUGGESTED_PROMPTS = [
  'Show me rentals in London under £2000',
  'Find a 3-bedroom apartment in Paris',
  'What are the cheapest properties in Berlin?',
  'Properties within 10km of Amsterdam',
  'Compare prices in London vs Paris',
  'Show houses for sale in Rome',
];

export default function FreeChatPreview() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '0',
      role: 'ai',
      content: 'Welcome to Lumina Estates AI Concierge. Ask me anything about properties in London, Paris, Berlin, Amsterdam, or Rome — I can search, filter, compare, and rank listings for you.',
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;
    setError(null);

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text.trim(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      if (!user) throw new Error('Please sign in to use the property assistant.');
      const response = await chatApi.sendMessage({ session_id: sessionId, message: text.trim() });

      // Persist session ID for follow-up turns
      if (!sessionId) setSessionId(response.session_id);

      const aiMsg: Message = {
        id: `a-${Date.now()}`,
        role: 'ai',
        content: response.clarification_needed
          ? (response.clarification_question || response.assistant_message)
          : response.assistant_message,
        response,
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to reach the AI assistant. Is the backend running?');
      const errMsg: Message = {
        id: `e-${Date.now()}`,
        role: 'ai',
        content: 'Sorry, I could not process that request. Please try again.',
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, sessionId, user]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    sendMessage(input);
  };

  return (
    <div className="container py-8 h-[calc(100vh-4rem)] flex flex-col max-w-4xl">
      {/* Header */}
      <div className="mb-5 flex items-center justify-between border-b pb-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-outfit flex items-center gap-2">
            <MessageSquare className="h-8 w-8 text-accent" />
            AI Concierge Chat
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            NL2SQL assistant · Phase 4 prototype
            {sessionId && (
              <span className="ml-2 font-mono text-xs opacity-50">
                session: {sessionId.slice(0, 8)}…
              </span>
            )}
          </p>
        </div>
        {sessionId && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => { setSessionId(null); setMessages([messages[0]]); }}
          >
            New session
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-5 flex-1 min-h-0">
        {/* Sidebar */}
        <div className="hidden md:flex md:col-span-1 flex-col border-r pr-5 gap-4">
          <div>
            <h3 className="font-semibold mb-3 text-xs uppercase tracking-wider text-muted-foreground">
              Try asking
            </h3>
            <div className="space-y-2">
              {SUGGESTED_PROMPTS.map((p, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(p)}
                  disabled={isLoading}
                  className="block w-full text-left p-2.5 rounded-lg bg-secondary/30 hover:bg-secondary/70 transition-colors text-xs border disabled:opacity-40"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          {/* Follow-up hints */}
          <div>
            <h3 className="font-semibold mb-3 text-xs uppercase tracking-wider text-muted-foreground">
              Follow-ups
            </h3>
            <div className="space-y-2">
              {['Show me cheaper ones', 'What about larger ones?', 'Within 20km instead', 'Show only apartments'].map((p, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(p)}
                  disabled={isLoading || !sessionId}
                  className="block w-full text-left p-2.5 rounded-lg bg-secondary/10 hover:bg-secondary/50 transition-colors text-xs border border-dashed disabled:opacity-30"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Chat area */}
        <div className="md:col-span-3 flex flex-col h-full bg-card border rounded-2xl shadow-sm overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5" ref={scrollRef}>
            {messages.map(msg => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}
            {isLoading && <TypingIndicator />}
          </div>

          {/* Error banner */}
          {error && (
            <div className="px-5 py-2 bg-destructive/10 text-destructive text-xs border-t">
              {error}
            </div>
          )}

          {/* Input */}
          <div className="p-4 bg-background border-t">
            {/* Mobile chips */}
            <div className="flex gap-2 overflow-x-auto pb-2 md:hidden">
              {SUGGESTED_PROMPTS.slice(0, 3).map((p, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(p)}
                  disabled={isLoading}
                  className="shrink-0 text-xs px-3 py-1.5 rounded-full bg-secondary/50 border hover:bg-secondary transition-colors"
                >
                  {p}
                </button>
              ))}
            </div>
            <form onSubmit={handleSubmit} className="relative flex items-center mt-1">
              <Input
                className="pr-12 h-13 rounded-full border-border/60 bg-secondary/20 shadow-inner text-sm"
                placeholder="Ask about properties…"
                value={input}
                onChange={e => setInput(e.target.value)}
                disabled={isLoading}
              />
              <Button
                type="submit"
                size="icon"
                className="absolute right-2 h-9 w-9 rounded-full"
                disabled={!input.trim() || isLoading}
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
