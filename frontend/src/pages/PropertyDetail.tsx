import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '@/services/api';
import { Property } from '@/types';
import { Button } from '@/components/ui/button';
import { BedDouble, Bath, Square, MapPin, ArrowLeft, Ruler, Building, Info, Heart } from 'lucide-react';

export default function PropertyDetail() {
  const { id } = useParams<{ id: string }>();
  const [property, setProperty] = useState<Property | null>(null);
  const [loading, setLoading] = useState(true);

  const [error, setError] = useState(false);

  useEffect(() => {
    async function loadProperty() {
      if (!id) return;
      try {
        setLoading(true);
        setError(false);
        const data = await api.getPropertyById(parseInt(id));
        setProperty(data);
      } catch (err) {
        console.error("Failed to load property", err);
        setError(true);
      } finally {
        setLoading(false);
      }
    }
    loadProperty();
  }, [id]);

  if (loading) {
    return (
      <div className="container py-32 grid grid-cols-1 lg:grid-cols-3 gap-12 animate-pulse">
        <div className="lg:col-span-2 space-y-8">
          <div className="h-[50vh] bg-secondary/50 rounded-2xl" />
          <div className="h-12 bg-secondary/50 rounded w-1/2" />
          <div className="h-6 bg-secondary/50 rounded w-1/4" />
        </div>
        <div className="lg:col-span-1">
          <div className="h-64 bg-secondary/50 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (error || !property) {
    return (
      <div className="container py-32 text-center flex flex-col items-center">
        <div className="w-16 h-16 bg-destructive/10 text-destructive rounded-full flex items-center justify-center mb-6">
          <Info className="h-8 w-8" />
        </div>
        <h2 className="text-2xl font-bold mb-4 font-outfit">Property Not Found</h2>
        <p className="text-muted-foreground max-w-md mb-8">
          We couldn't locate this property. It may have been removed, or there might be an issue connecting to the platform.
        </p>
        <Button variant="luxury" asChild><Link to="/properties">Return to Collection</Link></Button>
      </div>
    );
  }

  const imageCount = 4;
  const safeId = property?.id || 1;
  const imageIndex = (safeId % imageCount) + 1;
  const propType = property?.property_type?.toLowerCase() || 'apartment';
  const imageUrl = propType === 'house' 
    ? `/images/houses/house_0${imageIndex}.webp` 
    : `/images/apartments/apartment_0${imageIndex}.webp`;

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(price);
  };

  return (
    <div className="bg-background min-h-screen pb-20">
      {/* Hero Image */}
      <div className="relative h-[60vh] md:h-[70vh] w-full">
        <img 
          src={imageUrl} 
          alt={property.title} 
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-background/90 via-background/20 to-transparent" />
        
        <div className="absolute top-6 left-6 z-10">
          <Button variant="outline" className="bg-background/50 backdrop-blur border-border/50 hover:bg-background/80 text-foreground font-semibold" asChild>
            <Link to="/properties"><ArrowLeft className="h-5 w-5 mr-2" /> Back to Listings</Link>
          </Button>
        </div>
        <div className="absolute top-6 right-6 z-10">
          <Button variant="outline" size="icon" className="bg-background/50 backdrop-blur border-border/50 hover:bg-background/80 text-rose-500 hover:text-rose-600">
            <Heart className="h-5 w-5" />
          </Button>
        </div>

        <div className="absolute bottom-0 left-0 right-0 container pb-10 pt-32">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
            <div className="max-w-3xl">
              <div className="flex gap-3 mb-4">
                <span className="bg-primary text-primary-foreground px-4 py-1.5 text-sm font-semibold rounded-full uppercase tracking-widest">
                  For {property.intent}
                </span>
                <span className="bg-accent text-accent-foreground px-4 py-1.5 text-sm font-semibold rounded-full capitalize tracking-widest">
                  {property.property_type}
                </span>
              </div>
              <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-4 font-outfit tracking-tight">
                {property.title}
              </h1>
              <div className="flex items-center text-muted-foreground text-lg">
                <MapPin className="h-5 w-5 mr-2 text-accent" />
                <span>{property.neighbourhood}, {property.city}</span>
              </div>
            </div>
            
            <div className="bg-card/80 backdrop-blur-md p-6 rounded-2xl border shadow-lg shrink-0">
              <div className="text-sm text-muted-foreground uppercase tracking-widest font-semibold mb-1">Asking Price</div>
              <div className="text-4xl font-bold font-outfit text-primary">{formatPrice(property.price)}</div>
              <Button size="lg" className="w-full mt-6 luxury-btn">Schedule Viewing</Button>
            </div>
          </div>
        </div>
      </div>

      <div className="container mt-12 grid grid-cols-1 lg:grid-cols-3 gap-12">
        <div className="lg:col-span-2 space-y-12">
          {/* Key Metrics */}
          <section className="bg-secondary/20 rounded-3xl p-8 border">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              <div className="flex flex-col items-center text-center">
                <BedDouble className="h-8 w-8 text-accent mb-3" />
                <div className="text-2xl font-bold">{property.bedrooms}</div>
                <div className="text-muted-foreground text-sm uppercase tracking-wider">Bedrooms</div>
              </div>
              <div className="flex flex-col items-center text-center">
                <Bath className="h-8 w-8 text-accent mb-3" />
                <div className="text-2xl font-bold">{property.bathrooms}</div>
                <div className="text-muted-foreground text-sm uppercase tracking-wider">Bathrooms</div>
              </div>
              <div className="flex flex-col items-center text-center">
                <Square className="h-8 w-8 text-accent mb-3" />
                <div className="text-2xl font-bold">{property.size_sqm}</div>
                <div className="text-muted-foreground text-sm uppercase tracking-wider">Square Meters</div>
              </div>
              <div className="flex flex-col items-center text-center">
                <Ruler className="h-8 w-8 text-accent mb-3" />
                <div className="text-2xl font-bold">{property.distance_from_city_km.toFixed(1)}</div>
                <div className="text-muted-foreground text-sm uppercase tracking-wider">Km to Center</div>
              </div>
            </div>
          </section>

          {/* Description */}
          <section>
            <div className="flex items-center gap-3 mb-6">
              <Info className="h-6 w-6 text-accent" />
              <h2 className="text-2xl font-bold font-outfit">About this property</h2>
            </div>
            <div className="prose prose-lg dark:prose-invert max-w-none text-muted-foreground leading-relaxed">
              {property.description.split('\n').map((paragraph, idx) => (
                <p key={idx} className="mb-4">{paragraph}</p>
              ))}
            </div>
          </section>
        </div>

        <div className="lg:col-span-1">
          {/* Sticky Agent Card */}
          <div className="sticky top-24 border rounded-3xl p-8 bg-card shadow-sm">
            <h3 className="text-xl font-bold mb-6 font-outfit">Interested in this property?</h3>
            <p className="text-muted-foreground text-sm mb-8">
              Our luxury property specialists are available to provide a private tour and answer any questions you may have.
            </p>
            
            <div className="space-y-4">
              <Button className="w-full" size="lg" variant="luxury">Contact Agent</Button>
              <Button className="w-full" size="lg" variant="outline">Request Floor Plan</Button>
            </div>
            
            <hr className="my-8" />
            
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-secondary overflow-hidden border-2 border-accent">
                {/* Agent placeholder */}
                <div className="w-full h-full bg-muted flex items-center justify-center text-xl font-bold text-muted-foreground">AE</div>
              </div>
              <div>
                <div className="font-semibold text-lg">Alexander Estate</div>
                <div className="text-sm text-accent font-medium">Senior Partner</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
