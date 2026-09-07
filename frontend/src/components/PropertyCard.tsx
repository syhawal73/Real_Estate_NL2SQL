import { Property } from '@/types';
import { Card, CardContent, CardFooter } from './ui/card';
import { BedDouble, Bath, Square, MapPin } from 'lucide-react';
import { Link } from 'react-router-dom';

interface PropertyCardProps {
  property: Property;
}

export function PropertyCard({ property }: PropertyCardProps) {
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
    <Link to={`/properties/${property.id}`} className="block group">
      <Card className="overflow-hidden h-full transition-all duration-300 hover:shadow-xl hover:-translate-y-1 border-border/50">
        <div className="relative aspect-[4/3] overflow-hidden">
          <img 
            src={imageUrl} 
            alt={property.title} 
            className="object-cover w-full h-full transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
          />
          <div className="absolute top-4 left-4">
            <span className="bg-primary/90 text-primary-foreground backdrop-blur-sm px-3 py-1 text-xs font-semibold rounded-full uppercase tracking-wider">
              For {property.intent}
            </span>
          </div>
          <div className="absolute top-4 right-4">
            <span className="bg-background/90 text-foreground backdrop-blur-sm px-3 py-1 text-xs font-semibold rounded-full capitalize tracking-wider shadow-sm">
              {property.property_type}
            </span>
          </div>
        </div>
        
        <CardContent className="p-5">
          <div className="flex items-start justify-between gap-4 mb-2">
            <h3 className="font-semibold text-lg leading-tight line-clamp-1 group-hover:text-accent transition-colors">
              {property.title}
            </h3>
          </div>
          
          <div className="flex items-center text-muted-foreground text-sm mb-3">
            <MapPin className="h-4 w-4 mr-1 shrink-0" />
            <span className="truncate">{property.neighbourhood}, {property.city}</span>
          </div>

          <p className="text-sm text-muted-foreground line-clamp-2 mb-4 h-10">
            {property.description}
          </p>

          <div className="text-2xl font-bold text-foreground mb-4 font-outfit">
            {formatPrice(property.price)}
          </div>
          
          <div className="grid grid-cols-3 gap-2 border-t pt-4">
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <BedDouble className="h-4 w-4" />
              <span className="text-sm font-medium">{property.bedrooms} Beds</span>
            </div>
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Bath className="h-4 w-4" />
              <span className="text-sm font-medium">{property.bathrooms} Baths</span>
            </div>
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Square className="h-4 w-4" />
              <span className="text-sm font-medium">{property.size_sqm} m²</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
