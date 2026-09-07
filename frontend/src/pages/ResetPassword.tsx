import { FormEvent, useState } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { authApi } from '@/services/api';

export default function ResetPassword() {
  const [params] = useSearchParams(); const navigate = useNavigate(); const token = params.get('token') || '';
  const [password, setPassword] = useState(''); const [error, setError] = useState(''); const [done, setDone] = useState(false);
  async function submit(e: FormEvent) { e.preventDefault(); setError(''); try { await authApi.resetPassword(token, password); setDone(true); setTimeout(()=>navigate('/login'), 500); } catch (err:any) { setError(err?.response?.data?.detail || 'Invalid reset link'); } }
  return <div className="container max-w-md py-20"><div className="bg-card border rounded-2xl p-8"><h1 className="text-3xl font-bold mb-2">Choose a new password</h1>{done ? <p className="text-sm">Password updated. Redirecting to sign in…</p> : <form onSubmit={submit} className="space-y-5 mt-8"><div><Label htmlFor="password">New password</Label><Input id="password" type="password" minLength={10} value={password} onChange={e=>setPassword(e.target.value)} required className="mt-2" /></div>{error && <p className="text-sm text-destructive">{error}</p>}<Button type="submit" variant="luxury" className="w-full">Update password</Button><Link to="/login" className="block text-sm text-muted-foreground">Back to sign in</Link></form>}</div></div>;
}
