export type Role = 'USER' | 'ADMIN';
export type FoodCategory = 'noodle' | 'seafood' | 'snack' | 'dessert' | 'drink' | 'other';
export type TargetType = 'FOOD' | 'RESTAURANT';
export type ItinerarySource = 'AI' | 'FALLBACK';

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  createdAt: string;
  isBanned: boolean;
  banReason?: string | null;
}

export interface Food {
  id: number;
  slug: string;
  name: string;
  aiLabel: string;
  description: string;
  category: FoodCategory;
  imageUrl: string;
  priceMin: number;
  priceMax: number;
  isActive: boolean;
}

export interface Restaurant {
  id: number;
  slug: string;
  name: string;
  address: string;
  district: string;
  lat: number;
  lng: number;
  phone?: string | null;
  openTime: string;
  closeTime: string;
  priceLevel: 1 | 2 | 3;
  imageUrl: string;
  description: string;
  mealSlots: MealSlot[];
  ratingAvg: number;
  ratingCount: number;
  isFavorite?: boolean;
  price?: number | null;
  isSignature?: boolean;
  isActive: boolean;
}

export type MealSlot = 'breakfast' | 'lunch' | 'snack' | 'dinner';

export interface Review {
  id: number;
  rating: number;
  comment: string;
  createdAt: string;
  user: Pick<User, 'id' | 'name'>;
}

export interface RestaurantDetail extends Restaurant {
  foods: Array<Food & { price?: number | null; isSignature?: boolean }>;
}

export interface FoodDetail extends Food {
  restaurants: Restaurant[];
}

export interface Article {
  id: number;
  slug: string;
  title: string;
  summary: string;
  content: string;
  coverUrl: string;
  isPublished: boolean;
  publishedAt?: string | null;
}

export interface SearchMatch {
  food: Food;
  confidence: number;
  restaurants: Restaurant[];
}

export interface SearchResult {
  foods: SearchMatch[];
  unmatched: string[];
}

export interface SearchHistory {
  id: number;
  createdAt: string;
  foods: Food[];
}

export interface ItineraryStop {
  slot: 'breakfast' | 'lunch' | 'snack' | 'dinner';
  restaurant: Restaurant;
  food?: Food;
  reason: string;
}

export interface Itinerary {
  id: number;
  date: string;
  source: ItinerarySource;
  plan: ItineraryStop[];
  createdAt?: string;
}

export interface PageMeta {
  page: number;
  limit: number;
  total: number;
}

export interface PageResult<T> {
  items: T[];
  meta: PageMeta;
}

export interface AuthResult {
  token: string;
  user: User;
}

export interface HealthStatus {
  status: 'ok';
}

export interface AdminStats {
  users: number;
  restaurants: number;
  foods: number;
  reviews: number;
  searches7d: number;
}

export interface AdminUser extends User {
  createdAt: string;
}

export interface RestaurantInput {
  name: string;
  slug: string;
  address: string;
  district: string;
  lat?: number | null;
  lng?: number | null;
  phone?: string | null;
  openTime: string;
  closeTime: string;
  priceLevel: 1 | 2 | 3;
  imageUrl: string;
  description: string;
  mealSlots: MealSlot[];
}

export interface FoodInput {
  name: string;
  slug: string;
  aiLabel: string;
  description: string;
  category: FoodCategory;
  imageUrl: string;
  priceMin: number;
  priceMax: number;
}

export interface ArticleInput {
  slug: string;
  title: string;
  summary: string;
  content: string;
  coverUrl: string;
  isPublished: boolean;
}

export interface FavoriteList {
  foods: Food[];
  restaurants: Restaurant[];
}
