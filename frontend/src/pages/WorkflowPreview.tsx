import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Sparkles, Bot, Loader2 } from 'lucide-react';
import { api } from '@/services/api';
import { Property, PropertySearchParams } from '@/types';
import { PropertyCard } from '@/components/PropertyCard';

export default function WorkflowPreview() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Property[] | null>(null);
  
  // UI State matching workflow requirements
  const [intent, setIntent] = useState('');
  const [city, setCity] = useState('');
  const [budget, setBudget] = useState('');
  const [bedrooms, setBedrooms] = useState('');
  const [radius, setRadius] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResults(null);
    
    // Simulate AI processing time
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    try {
      const params: PropertySearchParams = {};
      if (intent) params.intent = intent as 'rent' | 'buy';
      if (city) params.city = city;
      if (budget) params.max_price = parseInt(budget);
      if (bedrooms) params.bedrooms = parseInt(bedrooms);
      if (radius) params.radius_km = parseFloat(radius);
      
      const data = await api.searchProperties(params);
      setResults(data.items);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container py-12 max-w-5xl">
      <div className="text-center mb-12">
        <div className="inline-flex items-center justify-center p-3 bg-accent/10 rounded-full mb-4">
          <Sparkles className="h-8 w-8 text-accent" />
        </div>
        <h1 className="text-4xl font-bold tracking-tight mb-4 font-outfit">Property Discovery Preview</h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Set your parameters, and preview how our upcoming tool will curate the perfect properties for you.
        </p>
      </div>

      <div className="grid md:grid-cols-12 gap-8">
        <div className="md:col-span-5">
          <Card className="border-accent/20 shadow-xl relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-accent/40 via-accent to-accent/40" />
            <CardContent className="p-8">
              <form onSubmit={handleSubmit} className="space-y-6">
                
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground/80">I want to...</label>
                  <Select value={intent} onChange={e => setIntent(e.target.value)} required>
                    <option value="">Select intent</option>
                    <option value="buy">Purchase a property</option>
                    <option value="rent">Rent a property</option>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground/80">In which city?</label>
                  <Input 
                    placeholder="e.g. London" 
                    value={city}
                    onChange={e => setCity(e.target.value)}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground/80">Maximum Budget</label>
                  <Input 
                    type="number"
                    placeholder="e.g. 5000000" 
                    value={budget}
                    onChange={e => setBudget(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground/80">Minimum Bedrooms</label>
                  <Input 
                    type="number"
                    placeholder="e.g. 3" 
                    value={bedrooms}
                    onChange={e => setBedrooms(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground/80">Max distance from center (km)</label>
                  <Input 
                    type="number"
                    placeholder="e.g. 5" 
                    value={radius}
                    onChange={e => setRadius(e.target.value)}
                  />
                </div>

                <Button type="submit" variant="luxury" className="w-full h-12 text-lg" disabled={loading}>
                  {loading ? (
                    <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Fetching...</>
                  ) : (
                    <><Bot className="mr-2 h-5 w-5" /> Search Preview</>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        <div className="md:col-span-7">
          <div className="bg-secondary/10 border rounded-2xl h-full p-6 min-h-[500px]">
            {!loading && !results && (
              <div className="h-full flex flex-col items-center justify-center text-center opacity-50">
                <Bot className="h-16 w-16 mb-4 text-muted-foreground" />
                <p className="text-lg font-medium">Waiting for your criteria...</p>
                <p className="text-sm">The results will display here.</p>
              </div>
            )}
            
            {loading && (
              <div className="h-full flex flex-col items-center justify-center text-center text-accent">
                <Loader2 className="h-12 w-12 animate-spin mb-4" />
                <p className="text-lg font-medium animate-pulse">Running Discovery Workflow...</p>
              </div>
            )}

            {results && (
              <div>
                <h3 className="text-2xl font-bold mb-6 font-outfit border-b pb-4">
                  Curated Results ({results.length})
                </h3>
                {results.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {results.slice(0, 4).map(property => (
                      <PropertyCard key={property.id} property={property} />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <p className="text-muted-foreground">No perfect match found for these strict criteria. Try adjusting your parameters.</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
