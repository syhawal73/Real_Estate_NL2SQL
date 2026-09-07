import { useEffect, useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '@/services/api';
import { Property, City, PropertySearchParams } from '@/types';
import { PropertyCard } from '@/components/PropertyCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { SlidersHorizontal, SearchX, X } from 'lucide-react';

export default function Listings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [properties, setProperties] = useState<Property[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [sortOption, setSortOption] = useState('newest');

  // Form states
  const [city, setCity] = useState(searchParams.get('city') || '');
  const [neighbourhood, setNeighbourhood] = useState(searchParams.get('neighbourhood') || '');
  const [intent, setIntent] = useState(searchParams.get('intent') || '');
  const [propertyType, setPropertyType] = useState(searchParams.get('property_type') || '');
  const [bedrooms, setBedrooms] = useState(searchParams.get('bedrooms') || '');
  const [maxPrice, setMaxPrice] = useState(searchParams.get('max_price') || '');
  const [radius, setRadius] = useState(searchParams.get('radius_km') || '');

  const fetchProperties = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: PropertySearchParams = {};
      
      const currentCity = searchParams.get('city');
      const currentNeighbourhood = searchParams.get('neighbourhood');
      const currentIntent = searchParams.get('intent');
      const currentType = searchParams.get('property_type');
      const currentBeds = searchParams.get('bedrooms');
      const currentPrice = searchParams.get('max_price');
      const currentRadius = searchParams.get('radius_km');

      if (currentCity) params.city = currentCity;
      if (currentNeighbourhood) params.neighbourhood = currentNeighbourhood;
      if (currentIntent) params.intent = currentIntent as 'rent' | 'buy';
      if (currentType) params.property_type = currentType as 'apartment' | 'house';
      if (currentBeds) params.bedrooms = parseInt(currentBeds);
      if (currentPrice) params.max_price = parseInt(currentPrice);
      if (currentRadius) params.radius_km = parseFloat(currentRadius);
      
      params.limit = 50; 
      
      const data = await api.searchProperties(params);
      setProperties(data.items);
    } catch (err) {
      console.error("Failed to search properties", err);
      setError("Unable to load properties. Please verify your connection.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    api.getCities().then(setCities).catch(console.error);
  }, []);

  useEffect(() => {
    fetchProperties();
  }, [searchParams]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const newParams = new URLSearchParams();
    if (city) newParams.set('city', city);
    if (neighbourhood) newParams.set('neighbourhood', neighbourhood);
    if (intent) newParams.set('intent', intent);
    if (propertyType) newParams.set('property_type', propertyType);
    if (bedrooms) newParams.set('bedrooms', bedrooms);
    if (maxPrice) newParams.set('max_price', maxPrice);
    if (radius) newParams.set('radius_km', radius);
    
    setSearchParams(newParams);
    setShowFilters(false);
  };

  const handleReset = () => {
    setCity('');
    setNeighbourhood('');
    setIntent('');
    setPropertyType('');
    setBedrooms('');
    setMaxPrice('');
    setRadius('');
    setSearchParams(new URLSearchParams());
  };

  const removeFilter = (key: string) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.delete(key);
    setSearchParams(newParams);
    
    // Update local state to match
    if (key === 'city') setCity('');
    if (key === 'neighbourhood') setNeighbourhood('');
    if (key === 'intent') setIntent('');
    if (key === 'property_type') setPropertyType('');
    if (key === 'bedrooms') setBedrooms('');
    if (key === 'max_price') setMaxPrice('');
    if (key === 'radius_km') setRadius('');
  };

  // Generate active filter chips
  const activeFilters = useMemo(() => {
    const filters = [];
    if (searchParams.get('city')) filters.push({ key: 'city', label: searchParams.get('city') });
    if (searchParams.get('neighbourhood')) filters.push({ key: 'neighbourhood', label: searchParams.get('neighbourhood') });
    if (searchParams.get('intent')) filters.push({ key: 'intent', label: searchParams.get('intent') === 'buy' ? 'For Sale' : 'For Rent' });
    if (searchParams.get('property_type')) filters.push({ key: 'property_type', label: searchParams.get('property_type') === 'house' ? 'House' : 'Apartment' });
    if (searchParams.get('bedrooms')) filters.push({ key: 'bedrooms', label: `${searchParams.get('bedrooms')}+ Beds` });
    if (searchParams.get('max_price')) filters.push({ key: 'max_price', label: `Max $${parseInt(searchParams.get('max_price')!).toLocaleString()}` });
    if (searchParams.get('radius_km')) filters.push({ key: 'radius_km', label: `< ${searchParams.get('radius_km')} km from center` });
    return filters;
  }, [searchParams]);

  const sortedProperties = useMemo(() => {
    const props = [...properties];
    if (sortOption === 'price_asc') {
      props.sort((a, b) => a.price - b.price);
    } else if (sortOption === 'price_desc') {
      props.sort((a, b) => b.price - a.price);
    }
    // 'newest' will just leave it as is, or you could sort by ID if desired
    return props;
  }, [properties, sortOption]);

  return (
    <div className="container py-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-4xl font-bold tracking-tight mb-2 font-outfit">Exclusive Collection</h1>
          <p className="text-muted-foreground">Find your perfect luxury residence</p>
        </div>
        <Button variant="outline" onClick={() => setShowFilters(!showFilters)} className="lg:hidden w-full md:w-auto">
          <SlidersHorizontal className="mr-2 h-4 w-4" /> Filters
        </Button>
      </div>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Sidebar Filters */}
        <div className={`lg:w-1/4 ${showFilters ? 'block' : 'hidden lg:block'}`}>
          <div className="sticky top-24 border rounded-xl p-6 bg-card">
            <div className="flex items-center gap-2 mb-6 border-b pb-4">
              <SlidersHorizontal className="h-5 w-5 text-accent" />
              <h2 className="text-lg font-semibold">Refine Search</h2>
            </div>
            
            <form onSubmit={handleSearch} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="city">City</Label>
                <Select id="city" value={city} onChange={e => setCity(e.target.value)}>
                  <option value="">All Cities</option>
                  {cities.map(c => (
                    <option key={c.city} value={c.city}>{c.city}</option>
                  ))}
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="intent">Intent</Label>
                <Select id="intent" value={intent} onChange={e => setIntent(e.target.value)}>
                  <option value="">All</option>
                  <option value="buy">For Sale</option>
                  <option value="rent">For Rent</option>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="propertyType">Property Type</Label>
                <Select id="propertyType" value={propertyType} onChange={e => setPropertyType(e.target.value)}>
                  <option value="">All Types</option>
                  <option value="house">House</option>
                  <option value="apartment">Apartment</option>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="bedrooms">Min Bedrooms</Label>
                <Input 
                  id="bedrooms" 
                  type="number" 
                  placeholder="Any" 
                  min="1"
                  value={bedrooms}
                  onChange={e => setBedrooms(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="maxPrice">Max Price ($)</Label>
                <Input 
                  id="maxPrice" 
                  type="number" 
                  placeholder="No Max" 
                  min="1"
                  value={maxPrice}
                  onChange={e => setMaxPrice(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="radius">Radius from City Center (km)</Label>
                <Input 
                  id="radius" 
                  type="number" 
                  placeholder="Any Distance" 
                  min="0.1"
                  step="0.1"
                  value={radius}
                  onChange={e => setRadius(e.target.value)}
                />
              </div>

              <div className="pt-4 flex gap-2">
                <Button type="submit" variant="luxury" className="w-full">Apply Filters</Button>
                <Button type="button" variant="outline" onClick={handleReset}>Clear</Button>
              </div>
            </form>
          </div>
        </div>

        {/* Property Grid */}
        <div className="lg:w-3/4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div className="text-sm font-medium text-muted-foreground">
              {!loading && !error && `Showing ${sortedProperties.length} Properties`}
            </div>
            
            <div className="flex items-center gap-2">
              <Label htmlFor="sort" className="shrink-0">Sort by:</Label>
              <Select 
                id="sort" 
                value={sortOption} 
                onChange={e => setSortOption(e.target.value)}
                className="w-[180px]"
              >
                <option value="newest">Newest</option>
                <option value="price_asc">Price Low → High</option>
                <option value="price_desc">Price High → Low</option>
              </Select>
            </div>
          </div>

          {activeFilters.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-6">
              {activeFilters.map(filter => (
                <div key={filter.key} className="flex items-center gap-1 bg-secondary text-secondary-foreground px-3 py-1.5 rounded-full text-sm">
                  <span>{filter.label}</span>
                  <button onClick={() => removeFilter(filter.key)} className="hover:text-accent ml-1"><X className="h-3 w-3" /></button>
                </div>
              ))}
              <button onClick={handleReset} className="text-sm text-muted-foreground hover:text-foreground underline ml-2">Clear all</button>
            </div>
          )}

          {error ? (
            <div className="flex flex-col items-center justify-center py-20 text-center border rounded-2xl bg-destructive/10 text-destructive">
              <SearchX className="h-16 w-16 mb-4 opacity-50" />
              <h3 className="text-2xl font-semibold mb-2">API Unavailable</h3>
              <p className="max-w-sm mb-6">{error}</p>
              <Button variant="outline" onClick={fetchProperties} className="border-destructive/50 text-destructive hover:bg-destructive hover:text-destructive-foreground">Retry Connection</Button>
            </div>
          ) : loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {[1, 2, 3, 4, 5, 6].map(i => (
                <div key={i} className="border rounded-lg overflow-hidden bg-card animate-pulse">
                  <div className="aspect-[4/3] bg-secondary/50" />
                  <div className="p-5 space-y-4">
                    <div className="h-6 bg-secondary/50 rounded w-3/4" />
                    <div className="h-4 bg-secondary/50 rounded w-1/2" />
                    <div className="h-8 bg-secondary/50 rounded w-1/3" />
                    <div className="grid grid-cols-3 gap-2 pt-4 border-t">
                      <div className="h-4 bg-secondary/50 rounded" />
                      <div className="h-4 bg-secondary/50 rounded" />
                      <div className="h-4 bg-secondary/50 rounded" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : sortedProperties.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {sortedProperties.map(property => (
                <PropertyCard key={property.id} property={property} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center border border-dashed rounded-2xl bg-secondary/10">
              <SearchX className="h-16 w-16 text-muted-foreground/50 mb-4" />
              <h3 className="text-2xl font-semibold mb-2">No matching properties found.</h3>
              <p className="text-muted-foreground max-w-sm mb-6">
                Try increasing your budget or search radius to discover more luxury homes.
              </p>
              <Button variant="luxury" onClick={handleReset}>Clear all filters</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
