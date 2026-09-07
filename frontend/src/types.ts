export interface User {
  id: string;
  email: string;
  role: 'USER' | 'ADMIN';
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
  profile: Record<string, unknown>;
}

export interface Property {
  id: number;
  title: string;
  city: string;
  neighbourhood: string;
  intent: 'rent' | 'buy';
  price: number;
  bedrooms: number;
  bathrooms: number;
  size_sqm: number;
  property_type: 'apartment' | 'house';
  distance_from_city_km: number;
  description: string;
  property_url?: string;
  currency?: string;
}

export interface City {
  city: string;
  latitude: number;
  longitude: number;
}

export interface Neighbourhood {
  neighbourhood: string;
  city: string;
}

export interface PlatformStats {
  total_properties: number;
  total_cities: number;
}

export interface PropertySearchParams {
  city?: string;
  neighbourhood?: string;
  intent?: 'rent' | 'buy';
  min_price?: number;
  max_price?: number;
  bedrooms?: number;
  property_type?: 'apartment' | 'house';
  radius_km?: number;
  limit?: number;
  offset?: number;
}

export interface PropertyListResponse {
  items: Property[];
  count: number;
  limit: number;
  offset: number;
}

// Phase 4 — Free Chat
export interface ChatRequest {
  session_id?: string | null;
  message: string;
}

export interface PropertyResult {
  id: number;
  title: string;
  city: string;
  neighbourhood: string;
  intent: 'rent' | 'buy';
  price: number;
  bedrooms: number;
  bathrooms: number;
  size_sqm: number;
  property_type: 'apartment' | 'house';
  distance_from_city_km: number;
  description: string;
  property_url: string;
  currency: string;
}

export interface ChatResponse {
  session_id: string;
  user_message: string;
  assistant_message: string;
  intent?: string;
  generated_sql?: string;
  properties: PropertyResult[];
  clarification_needed: boolean;
  clarification_question?: string;
  result_count: number;
  error_message?: string;
  fallback_applied: boolean;
  fallback_message?: string;
  more_results_url?: string;
}
