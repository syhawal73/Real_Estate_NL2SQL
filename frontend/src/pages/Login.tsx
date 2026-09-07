import { FormEvent, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/auth/AuthContext';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault(); setError(''); setLoading(true);
    try {
      const user = await login(email, password);
      const next = new URLSearchParams(location.search).get('next') || (user.role === 'ADMIN' ? '/admin' : '/chat');
      navigate(next);
    } catch (err: any) { setError(err?.response?.data?.detail || 'Unable to sign in'); }
    finally { setLoading(false); }
  }

  return <div className="container max-w-md py-20">
    <div className="bg-card border rounded-2xl p-8 shadow-sm">
      <h1 className="text-3xl font-bold mb-2">Welcome back</h1>
      <p className="text-muted-foreground mb-8">Sign in to Lumina Estates.</p>
      <form onSubmit={submit} className="space-y-5">
        <div><Label htmlFor="email">Email</Label><Input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} required className="mt-2" /></div>
        <div><Label htmlFor="password">Password</Label><Input id="password" type="password" value={password} onChange={e => setPassword(e.target.value)} required className="mt-2" /></div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" variant="luxury" className="w-full" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</Button>
      </form>
      <div className="mt-6 text-sm text-muted-foreground flex justify-between"><Link to="/register" className="hover:text-accent">Create account</Link><Link to="/forgot-password" className="hover:text-accent">Forgot password?</Link></div>
    </div>
  </div>;
}
