import axios from 'axios';
import { Property, City, Neighbourhood, PlatformStats, PropertySearchParams, PropertyListResponse, User, ChatRequest, ChatResponse } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  getHealth: async () => {
    const response = await apiClient.get('/health');
    return response.data;
  },

  getStats: async (): Promise<PlatformStats> => {
    const response = await apiClient.get('/stats');
    return response.data;
  },

  getCities: async (): Promise<City[]> => {
    const response = await apiClient.get('/metadata/cities');
    return response.data;
  },

  getNeighbourhoods: async (city: string): Promise<Neighbourhood[]> => {
    const response = await apiClient.get(`/metadata/cities/${encodeURIComponent(city)}/neighbourhoods`);
    return response.data;
  },

  getProperties: async (limit: number = 50, offset: number = 0): Promise<PropertyListResponse> => {
    const response = await apiClient.get('/properties', { params: { limit, offset } });
    return response.data;
  },

  getPropertyById: async (id: number): Promise<Property> => {
    const response = await apiClient.get(`/properties/${id}`);
    return response.data;
  },

  searchProperties: async (params: PropertySearchParams): Promise<PropertyListResponse> => {
    // Phase 2 requires this to be a POST request. Wait, the prompt says POST /properties/search
    // Let's ensure it's a POST request and we send the body
    const response = await apiClient.post('/properties/search', params);
    return response.data;
  },
};

export const authApi = {
  me: async (): Promise<User> => (await apiClient.get('/auth/me')).data,
  login: async (email: string, password: string) => (await apiClient.post('/auth/login', { email, password })).data,
  register: async (email: string, password: string, fullName?: string) => (await apiClient.post('/auth/register', { email, password, full_name: fullName })).data,
  logout: async () => (await apiClient.post('/auth/logout')).data,
  logoutAll: async () => (await apiClient.post('/auth/logout-all')).data,
  forgotPassword: async (email: string) => (await apiClient.post('/auth/forgot-password', { email })).data,
  resetPassword: async (token: string, password: string) => (await apiClient.post('/auth/reset-password', { token, password })).data,
};

export const accountApi = {
  favorites: async () => (await apiClient.get('/account/favorites')).data,
  addFavorite: async (propertyId: number) => (await apiClient.post(`/account/favorites/${propertyId}`)).data,
  removeFavorite: async (propertyId: number) => (await apiClient.delete(`/account/favorites/${propertyId}`)).data,
  savedSearches: async () => (await apiClient.get('/account/saved-searches')).data,
  saveSearch: async (name: string, criteria: object) => (await apiClient.post('/account/saved-searches', { name, criteria })).data,
  recentlyViewed: async () => (await apiClient.get('/account/recently-viewed')).data,
  trackViewed: async (propertyId: number) => (await apiClient.post(`/account/recently-viewed/${propertyId}`)).data,
};

export const adminApi = {
  stats: async () => (await apiClient.get('/admin/stats')).data,
  properties: async (q?: string) => (await apiClient.get('/admin/properties', { params: q ? { q } : undefined })).data,
  createProperty: async (body: object) => (await apiClient.post('/admin/properties', body)).data,
  updateProperty: async (id: number, body: object) => (await apiClient.patch(`/admin/properties/${id}`, body)).data,
  deleteProperty: async (id: number) => (await apiClient.delete(`/admin/properties/${id}`)).data,
  users: async (q?: string) => (await apiClient.get('/admin/users', { params: q ? { q } : undefined })).data,
  createUser: async (body: object) => (await apiClient.post('/admin/users', body)).data,
  updateUser: async (id: string, body: object) => (await apiClient.patch(`/admin/users/${id}`, body)).data,
  conversations: async () => (await apiClient.get('/admin/conversations')).data,
  conversation: async (id: string) => (await apiClient.get(`/admin/conversations/${id}`)).data,
  auditLog: async () => (await apiClient.get('/admin/audit-log')).data,
  llmSettings: async () => (await apiClient.get('/admin/settings/llm')).data,
  updateLlmSettings: async (body: object) => (await apiClient.put('/admin/settings/llm', body)).data,
};

export const chatApi = {
  sendMessage: async (request: ChatRequest): Promise<ChatResponse> => {
    const response = await apiClient.post('/chat', request);
    return response.data;
  },
};
