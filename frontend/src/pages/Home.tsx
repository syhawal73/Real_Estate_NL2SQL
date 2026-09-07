import { useEffect, useState } from 'react';
import { api } from '@/services/api';
import { PlatformStats, Property, City } from '@/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { PropertyCard } from '@/components/PropertyCard';
import { Building2, Map as MapIcon, Search, Sparkles, MessageSquare } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { CountUp } from '@/components/ui/count-up';

export default function Home() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [featuredProperties, setFeaturedProperties] = useState<Property[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    async function loadData() {
      try {
        const [statsData, propsData, citiesData] = await Promise.all([
          api.getStats(),
          api.getProperties(3, 0), // Get 3 properties for featured
          api.getCities()
        ]);
        setStats(statsData);
        setFeaturedProperties(propsData.items);
        setCities(citiesData.slice(0, 4)); // Show up to 4 cities
      } catch (error) {
        console.error("Failed to load home page data", error);
      }
    }
    loadData();
  }, []);

  return (
    <div className="flex flex-col min-h-screen">
      {/* Hero Section */}
      <section className="relative h-[80vh] flex items-center justify-center overflow-hidden">
        <div className="absolute inset-0 bg-primary/90 z-10" />
        <img 
          src="/images/houses/house_01.webp" 
          alt="Luxury Real Estate" 
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="relative z-20 container text-center text-primary-foreground max-w-4xl mx-auto px-4">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tighter mb-6 font-outfit">
            Discover Your Next <span className="text-accent">Masterpiece</span>
          </h1>
          <p className="text-lg md:text-xl text-primary-foreground/80 mb-10 max-w-2xl mx-auto font-light">
            Curated luxury properties in the world's most prestigious locations. 
            Experience unparalleled elegance and sophisticated living.
          </p>
          <div className="bg-background/90 backdrop-blur-md p-4 rounded-2xl shadow-2xl max-w-3xl mx-auto flex flex-col md:flex-row gap-4 items-end">
            <div className="w-full text-left">
              <label className="text-xs font-semibold text-foreground uppercase tracking-wider mb-1 block">City</label>
              <select 
                className="w-full bg-transparent border-b border-border pb-2 focus:outline-none focus:border-accent text-foreground appearance-none"
                id="hero-city"
              >
                <option value="">Any City</option>
                {cities.map(c => <option key={c.city} value={c.city}>{c.city}</option>)}
              </select>
            </div>
            <div className="w-full text-left">
              <label className="text-xs font-semibold text-foreground uppercase tracking-wider mb-1 block">Intent</label>
              <select 
                className="w-full bg-transparent border-b border-border pb-2 focus:outline-none focus:border-accent text-foreground appearance-none"
                id="hero-intent"
              >
                <option value="">Buy or Rent</option>
                <option value="buy">Buy</option>
                <option value="rent">Rent</option>
              </select>
            </div>
            <div className="w-full text-left">
              <label className="text-xs font-semibold text-foreground uppercase tracking-wider mb-1 block">Type</label>
              <select 
                className="w-full bg-transparent border-b border-border pb-2 focus:outline-none focus:border-accent text-foreground appearance-none"
                id="hero-type"
              >
                <option value="">All Types</option>
                <option value="house">House</option>
                <option value="apartment">Apartment</option>
              </select>
            </div>
            <Button 
              size="lg" 
              variant="luxury" 
              className="w-full md:w-auto px-8"
              onClick={() => {
                const city = (document.getElementById('hero-city') as HTMLSelectElement).value;
                const intent = (document.getElementById('hero-intent') as HTMLSelectElement).value;
                const type = (document.getElementById('hero-type') as HTMLSelectElement).value;
                
                const params = new URLSearchParams();
                if (city) params.set('city', city);
                if (intent) params.set('intent', intent);
                if (type) params.set('property_type', type);
                
                navigate(`/properties?${params.toString()}`);
              }}
            >
              Search Properties
            </Button>
          </div>
        </div>
      </section>

      {/* Statistics Section */}
      <section className="py-16 bg-background">
        <div className="container">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <Card className="bg-secondary/50 border-none shadow-none text-center p-8">
              <CardContent className="p-0">
                <Building2 className="h-12 w-12 mx-auto mb-4 text-accent" />
                <div className="text-5xl font-bold text-primary mb-2 font-outfit">
                  {stats ? <><CountUp end={stats.total_properties} />+</> : '...'}
                </div>
                <div className="text-sm uppercase tracking-widest text-muted-foreground font-semibold">
                  Exclusive Properties
                </div>
              </CardContent>
            </Card>
            <Card className="bg-secondary/50 border-none shadow-none text-center p-8">
              <CardContent className="p-0">
                <MapIcon className="h-12 w-12 mx-auto mb-4 text-accent" />
                <div className="text-5xl font-bold text-primary mb-2 font-outfit">
                  {stats ? <CountUp end={stats.total_cities} /> : '...'}
                </div>
                <div className="text-sm uppercase tracking-widest text-muted-foreground font-semibold">
                  Global Cities
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Featured Properties */}
      <section className="py-20 bg-secondary/20">
        <div className="container">
          <div className="flex justify-between items-end mb-12">
            <div>
              <h2 className="text-3xl font-bold tracking-tight mb-2">Featured Collection</h2>
              <p className="text-muted-foreground">Handpicked properties of exceptional quality.</p>
            </div>
            <Button variant="ghost" asChild className="hidden md:flex">
              <Link to="/properties">View All <Search className="ml-2 h-4 w-4" /></Link>
            </Button>
          </div>
          
          {featuredProperties.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {featuredProperties.map(property => (
                <PropertyCard key={property.id} property={property} />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-muted-foreground">Loading featured properties...</div>
          )}
          
          <Button variant="outline" asChild className="w-full mt-8 md:hidden">
            <Link to="/properties">View All Properties</Link>
          </Button>
        </div>
      </section>

      {/* Explore by City */}
      <section className="py-20 bg-background border-t">
        <div className="container">
          <h2 className="text-3xl font-bold tracking-tight mb-12 text-center">Explore by City</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {cities.map(city => (
              <Link key={city.city} to={`/properties?city=${encodeURIComponent(city.city)}`} className="group">
                <Card className="relative overflow-hidden h-40 border-none">
                  <div className="absolute inset-0 bg-primary/60 transition-opacity group-hover:bg-primary/40 z-10" />
                  <img src="/images/apartments/apartment.jpg" alt={city.city} className="absolute inset-0 w-full h-full object-cover grayscale transition-transform duration-700 group-hover:scale-110" />
                  <div className="absolute inset-0 z-20 flex items-center justify-center">
                    <h3 className="text-2xl font-bold text-white tracking-wider font-outfit">{city.city}</h3>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* AI Previews */}
      <section className="py-20 bg-primary text-primary-foreground">
        <div className="container">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-3xl font-bold tracking-tight mb-4">Experience the Future of Real Estate</h2>
            <p className="text-primary-foreground/70">
              Our upcoming property discovery tools are designed to understand your unique lifestyle needs and find the perfect match.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <Card className="bg-primary-foreground/5 border-primary-foreground/10 text-primary-foreground backdrop-blur flex flex-col h-full">
              <CardContent className="p-8 flex-1">
                <Sparkles className="h-10 w-10 text-accent mb-6" />
                <h3 className="text-2xl font-bold mb-3">Property Discovery Preview</h3>
                <p className="text-primary-foreground/60 mb-8">
                  Explore our upcoming property matching experience. Simply set your parameters, and we'll handle the complex filtering across thousands of listings.
                </p>
                <Button variant="luxury" asChild className="w-full mt-auto">
                  <Link to="/workflow">Try Discovery Preview</Link>
                </Button>
              </CardContent>
            </Card>

            <Card className="bg-primary-foreground/5 border-primary-foreground/10 text-primary-foreground backdrop-blur flex flex-col h-full">
              <CardContent className="p-8 flex-1">
                <MessageSquare className="h-10 w-10 text-accent mb-6" />
                <h3 className="text-2xl font-bold mb-3">Free Chat Preview</h3>
                <p className="text-primary-foreground/60 mb-8">
                  Get a sneak peek at our future real estate concierge interface. A conversational way to ask questions about neighbourhoods or specific property details.
                </p>
                <Button variant="outline" asChild className="w-full mt-auto border-primary-foreground/20 bg-transparent hover:bg-primary-foreground/10 text-primary-foreground hover:text-primary-foreground">
                  <Link to="/chat">Try Chat Preview</Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>
    </div>
  );
}
