import { Link } from 'react-router-dom';
import { Home, UserCircle, Shield } from 'lucide-react';
import { useAuth } from '@/auth/AuthContext';
import { Button } from '@/components/ui/button';

export function Navbar() {
  const { user, logout } = useAuth();
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between">
        <div className="flex items-center gap-2">
          <Home className="h-6 w-6 text-accent" />
          <Link to="/" className="font-bold text-xl tracking-tight text-primary">
            Lumina Estates
          </Link>
        </div>
        <nav className="flex items-center gap-6 text-sm font-medium">
          <Link to="/" className="transition-colors hover:text-accent">Home</Link>
          <Link to="/properties" className="transition-colors hover:text-accent">Properties</Link>
          <Link to="/workflow" className="transition-colors hover:text-accent">Workflow AI</Link>
          {user && <Link to="/chat" className="transition-colors hover:text-accent">Chat AI</Link>}
          {user?.role === 'ADMIN' && <Link to="/admin" className="transition-colors hover:text-accent flex items-center gap-1"><Shield className="h-4 w-4" />Admin</Link>}
          {!user ? <Link to="/login" className="transition-colors hover:text-accent flex items-center gap-1"><UserCircle className="h-4 w-4" />Sign in</Link> : <Button variant="ghost" size="sm" onClick={() => void logout()}>Sign out</Button>}
        </nav>
      </div>
    </header>
  );
}
