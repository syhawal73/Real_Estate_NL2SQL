import { FormEvent, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Link } from 'react-router-dom';
import { authApi } from '@/services/api';

export default function ForgotPassword() {
  const [email, setEmail] = useState(''); const [done, setDone] = useState(false); const [error, setError] = useState('');
  async function submit(e: FormEvent) { e.preventDefault(); setError(''); try { await authApi.forgotPassword(email); setDone(true); } catch (err:any) { setError(err?.response?.data?.detail || 'Unable to submit request'); } }
  return <div className="container max-w-md py-20"><div className="bg-card border rounded-2xl p-8"><h1 className="text-3xl font-bold mb-2">Reset password</h1><p className="text-muted-foreground mb-8">We’ll email you a reset link.</p>{done ? <p className="text-sm">If the account exists, reset instructions have been sent.</p> : <form onSubmit={submit} className="space-y-5"><div><Label htmlFor="email">Email</Label><Input id="email" type="email" value={email} onChange={e=>setEmail(e.target.value)} required className="mt-2" /></div>{error && <p className="text-sm text-destructive">{error}</p>}<Button type="submit" variant="luxury" className="w-full">Send reset link</Button></form>}<Link to="/login" className="block mt-6 text-sm hover:text-accent">Back to sign in</Link></div></div>;
}
