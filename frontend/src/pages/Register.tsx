import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/auth/AuthContext';

export default function Register() {
  const { register } = useAuth(); const navigate = useNavigate();
  const [name, setName] = useState(''); const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [error, setError] = useState(''); const [done, setDone] = useState(false);
  async function submit(e: FormEvent) { e.preventDefault(); setError(''); try { await register(email, password, name); setDone(true); } catch (err: any) { setError(err?.response?.data?.detail || 'Unable to create account'); } }
  return <div className="container max-w-md py-20"><div className="bg-card border rounded-2xl p-8 shadow-sm">
    <h1 className="text-3xl font-bold mb-2">Create your account</h1><p className="text-muted-foreground mb-8">Get a personal property-search workspace.</p>
    {done ? <div className="space-y-4"><p className="text-sm">Account created. Check your email for the verification link.</p><Button variant="luxury" asChild><Link to="/login">Back to sign in</Link></Button></div> : <form onSubmit={submit} className="space-y-5">
      <div><Label htmlFor="name">Name</Label><Input id="name" value={name} onChange={e=>setName(e.target.value)} className="mt-2" /></div>
      <div><Label htmlFor="email">Email</Label><Input id="email" type="email" value={email} onChange={e=>setEmail(e.target.value)} required className="mt-2" /></div>
      <div><Label htmlFor="password">Password</Label><Input id="password" type="password" minLength={10} value={password} onChange={e=>setPassword(e.target.value)} required className="mt-2" /></div>
      {error && <p className="text-sm text-destructive">{error}</p>}<Button type="submit" variant="luxury" className="w-full">Create account</Button>
    </form>}
    <p className="mt-6 text-sm text-muted-foreground"><Link to="/login" className="hover:text-accent">Already have an account?</Link></p>
  </div></div>;
}
