import { useEffect, useState } from 'react';
import { adminApi } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { BarChart3, Building2, Users, MessageSquare, ScrollText, Settings2, Plus, Trash2 } from 'lucide-react';

const tabs = [
  ['overview', 'Overview', BarChart3], ['properties', 'Properties', Building2], ['users', 'Users', Users],
  ['conversations', 'Conversations', MessageSquare], ['audit', 'Audit log', ScrollText], ['llm', 'LLM', Settings2],
] as const;

export default function AdminDashboard() {
  const [tab, setTab] = useState<typeof tabs[number][0]>('overview');
  return <div className="container py-8 min-h-[calc(100vh-4rem)]">
    <div className="mb-8"><p className="text-xs uppercase tracking-[0.2em] text-accent font-semibold">Administration</p><h1 className="text-4xl font-bold mt-2">Lumina control room</h1><p className="text-muted-foreground mt-2">Manage listings, users, conversations and AI configuration.</p></div>
    <div className="flex flex-wrap gap-2 border-b pb-4 mb-6">{tabs.map(([key, label, Icon]) => <Button key={key} variant={tab===key ? 'default' : 'ghost'} onClick={()=>setTab(key)} className="gap-2"><Icon className="h-4 w-4" />{label}</Button>)}</div>
    {tab === 'overview' && <Overview />}
    {tab === 'properties' && <PropertiesPanel />}
    {tab === 'users' && <UsersPanel />}
    {tab === 'conversations' && <ConversationsPanel />}
    {tab === 'audit' && <AuditPanel />}
    {tab === 'llm' && <LlmPanel />}
  </div>;
}

function Overview() {
  const [stats, setStats] = useState<any>();
  useEffect(()=>{ void adminApi.stats().then(setStats); }, []);
  const cards = [['Properties', stats?.total_properties, Building2], ['Users', stats?.total_users, Users], ['Conversations', stats?.total_conversations, MessageSquare], ['Favorites', stats?.total_favorites, BarChart3]];
  return <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">{cards.map(([label, value, Icon])=><div key={label as string} className="bg-card border rounded-2xl p-6"><Icon className="h-5 w-5 text-accent mb-6"/><div className="text-3xl font-bold">{value ?? '—'}</div><p className="text-sm text-muted-foreground mt-1">{label as string}</p></div>)}</div>;
}

function PropertiesPanel() {
  const [items, setItems] = useState<any[]>([]); const [q, setQ] = useState(''); const [form, setForm] = useState(false);
  const load=()=>adminApi.properties(q).then((r:any)=>setItems(r.items)); useEffect(()=>{void load();},[]); 
  const [draft, setDraft] = useState<any>({title:'',city:'London',neighbourhood:'',intent:'rent',price:1000,bedrooms:1,bathrooms:1,size_sqm:40,property_type:'apartment',distance_from_city_km:1,description:''});
  async function create(){await adminApi.createProperty(draft); setForm(false); setDraft({...draft,title:'',description:''}); await load();}
  async function remove(id:number){if(!confirm(`Delete property ${id}?`)) return; await adminApi.deleteProperty(id); await load();}
  return <div className="space-y-6"><div className="flex gap-3"><Input placeholder="Search properties…" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&void load()} /><Button variant="luxury" onClick={()=>setForm(v=>!v)} className="gap-2"><Plus className="h-4 w-4"/>Add property</Button></div>{form&&<div className="grid md:grid-cols-3 gap-4 bg-card border rounded-2xl p-6">{[['title','Title'],['city','City'],['neighbourhood','Neighbourhood'],['price','Price'],['bedrooms','Bedrooms'],['bathrooms','Bathrooms'],['size_sqm','Size m²'],['distance_from_city_km','Distance km'],['description','Description']].map(([k,l])=><div key={k}><Label>{l}</Label><Input className="mt-2" value={draft[k]} onChange={e=>setDraft({...draft,[k]:['price','bedrooms','bathrooms','size_sqm','distance_from_city_km'].includes(k)?Number(e.target.value):e.target.value})}/></div>)}<div className="flex items-end"><Button variant="luxury" onClick={()=>void create()}>Create</Button></div></div>}
  <div className="overflow-x-auto border rounded-2xl bg-card"><table className="w-full text-sm"><thead className="bg-secondary/40"><tr><th className="text-left p-4">ID</th><th className="text-left p-4">Property</th><th className="text-left p-4">Location</th><th className="text-left p-4">Price</th><th className="p-4"/></tr></thead><tbody>{items.map(p=><tr key={p.id} className="border-t"><td className="p-4">{p.id}</td><td className="p-4 font-medium">{p.title}</td><td className="p-4">{p.neighbourhood}, {p.city}</td><td className="p-4">{p.price}</td><td className="p-4 text-right"><Button variant="ghost" size="icon" onClick={()=>void remove(p.id)}><Trash2 className="h-4 w-4 text-destructive"/></Button></td></tr>)}</tbody></table></div></div>;
}

function UsersPanel() {
  const [items,setItems]=useState<any[]>([]); const [q,setQ]=useState(''); const load=()=>adminApi.users(q).then(setItems); useEffect(()=>{void load();},[]);
  async function disable(user:any){if(!confirm(`Disable ${user.email}?`)) return; await adminApi.updateUser(user.id,{is_active:false}); await load();}
  return <div className="space-y-6"><div className="flex gap-3"><Input placeholder="Search by email…" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&void load()}/><Button onClick={()=>void load()}>Refresh</Button></div><div className="overflow-x-auto border rounded-2xl bg-card"><table className="w-full text-sm"><thead className="bg-secondary/40"><tr><th className="text-left p-4">Email</th><th className="text-left p-4">Role</th><th className="text-left p-4">Status</th><th className="p-4"/></tr></thead><tbody>{items.map(u=><tr key={u.id} className="border-t"><td className="p-4">{u.email}</td><td className="p-4">{u.role}</td><td className="p-4">{u.is_active?'Active':'Disabled'}</td><td className="p-4 text-right">{u.is_active&&u.role!=='ADMIN'&&<Button variant="outline" size="sm" onClick={()=>void disable(u)}>Disable</Button>}</td></tr>)}</tbody></table></div></div>;
}

function ConversationsPanel(){const [rows,setRows]=useState<any[]>([]); useEffect(()=>{void adminApi.conversations().then(setRows);},[]); return <div className="space-y-4">{rows.map(r=><div key={r.session_id} className="bg-card border rounded-2xl p-5"><div className="font-mono text-xs text-muted-foreground">{r.session_id}</div><div className="mt-2">User: {r.user_id}</div><div className="text-sm text-muted-foreground mt-1">Last active: {new Date(r.last_active).toLocaleString()}</div></div>)}</div>}
function AuditPanel(){const [rows,setRows]=useState<any[]>([]); useEffect(()=>{void adminApi.auditLog().then(setRows);},[]); return <div className="space-y-3">{rows.map(r=><div key={r.id} className="bg-card border rounded-xl p-4"><div className="font-medium">{r.action} {r.resource_type} {r.resource_id ? `#${r.resource_id}` : ''}</div><div className="text-sm text-muted-foreground mt-1">{new Date(r.created_at).toLocaleString()}</div></div>)}</div>}
function LlmPanel(){const [data,setData]=useState<any>({}); const [saved,setSaved]=useState(false); useEffect(()=>{void adminApi.llmSettings().then(setData);},[]); async function save(){await adminApi.updateLlmSettings(data);setSaved(true);setTimeout(()=>setSaved(false),1500);} return <div className="max-w-2xl bg-card border rounded-2xl p-6 space-y-5"><div><Label>Provider</Label><Input className="mt-2" value={data.provider||''} onChange={e=>setData({...data,provider:e.target.value})}/></div><div><Label>Model</Label><Input className="mt-2" value={data.model||''} onChange={e=>setData({...data,model:e.target.value})}/></div><div><Label>Base URL</Label><Input className="mt-2" value={data.base_url||''} onChange={e=>setData({...data,base_url:e.target.value})}/></div><div><Label>Temperature</Label><Input className="mt-2" type="number" step="0.1" value={data.temperature??''} onChange={e=>setData({...data,temperature:e.target.value})}/></div><div><Label>Max tokens</Label><Input className="mt-2" type="number" value={data.max_tokens??''} onChange={e=>setData({...data,max_tokens:e.target.value})}/></div><div><Label>API key</Label><Input className="mt-2" type="password" value={data.api_key||''} onChange={e=>setData({...data,api_key:e.target.value})} placeholder="Leave unchanged unless rotating"/></div><div className="flex items-center gap-3"><Button variant="luxury" onClick={()=>void save()}>Save configuration</Button>{saved&&<span className="text-sm text-green-700">Saved</span>}</div></div>}
