export function Footer() {
  return (
    <footer className="border-t bg-primary text-primary-foreground py-12 mt-auto">
      <div className="container grid gap-8 md:grid-cols-4">
        <div>
          <h3 className="text-lg font-semibold mb-4 text-accent">Lumina Estates</h3>
          <p className="text-sm text-primary-foreground/70">
            Discover the world's most luxurious properties, curated for the modern connoisseur.
          </p>
        </div>
        <div>
          <h4 className="text-sm font-semibold mb-4 text-accent">Explore</h4>
          <ul className="space-y-2 text-sm text-primary-foreground/70">
            <li><a href="/properties" className="hover:text-white transition-colors">All Properties</a></li>
            <li><a href="/properties?intent=buy" className="hover:text-white transition-colors">For Sale</a></li>
            <li><a href="/properties?intent=rent" className="hover:text-white transition-colors">For Rent</a></li>
          </ul>
        </div>
        <div>
          <h4 className="text-sm font-semibold mb-4 text-accent">AI Tools</h4>
          <ul className="space-y-2 text-sm text-primary-foreground/70">
            <li><a href="/workflow" className="hover:text-white transition-colors">Workflow Assistant</a></li>
            <li><a href="/chat" className="hover:text-white transition-colors">Free Chat</a></li>
          </ul>
        </div>
        <div>
          <h4 className="text-sm font-semibold mb-4 text-accent">Contact</h4>
          <ul className="space-y-2 text-sm text-primary-foreground/70">
            <li>info@luminaestates.com</li>
            <li>+1 (555) 123-4567</li>
            <li>100 Luxury Way, CA 90210</li>
          </ul>
        </div>
      </div>
      <div className="container mt-12 pt-8 border-t border-primary-foreground/10 text-center text-sm text-primary-foreground/50">
        &copy; {new Date().getFullYear()} Lumina Estates. All rights reserved.
      </div>
    </footer>
  );
}
