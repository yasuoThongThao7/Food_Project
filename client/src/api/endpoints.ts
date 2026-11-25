import { request, queryString } from './http';
import type {
  AdminStats, AdminUser, Article, ArticleInput, AuthResult, FavoriteList, Food, FoodDetail,
  FoodInput, HealthStatus, Itinerary, PageResult, Restaurant, RestaurantDetail, RestaurantInput, Review,
  PredictionResult, SearchHistory, User
} from './types';

export async function getHealth(): Promise<HealthStatus> {
  return (await request<HealthStatus>('GET /health')).data;
}

export async function register(input: { email: string; password: string; name: string }): Promise<AuthResult> {
  return (await request<AuthResult>('POST /auth/register', { method: 'POST', body: JSON.stringify(input) }, false)).data;
}

export async function login(input: { email: string; password: string }): Promise<AuthResult> {
  return (await request<AuthResult>('POST /auth/login', { method: 'POST', body: JSON.stringify(input) }, false)).data;
}

export async function getMe(): Promise<User> {
  return (await request<User>('GET /auth/me')).data;
}

export async function predictImage(image: Blob): Promise<PredictionResult> {
  const body = new FormData();
  body.append('file', image, 'food-prediction.jpg');
  return (await request<PredictionResult>(
    'POST /predict',
    { method: 'POST', body, signal: AbortSignal.timeout(90_000) },
    true,
    { retryWithoutAuthOn401: true }
  )).data;
}

export async function getSearchHistory(): Promise<SearchHistory[]> {
  return (await request<SearchHistory[]>('GET /search/history')).data;
}

export async function clearSearchHistory(): Promise<void> {
  await request<null>('DELETE /search/history', { method: 'DELETE' });
}

export async function getFoods(params: { q?: string; category?: string; page?: number; limit?: number } = {}): Promise<PageResult<Food>> {
  const result = await request<Food[]>('GET /foods' + queryString(params));
  return { items: result.data, meta: result.meta ?? { page: params.page ?? 1, limit: params.limit ?? 12, total: result.data.length } };
}

export async function getFood(id: number): Promise<FoodDetail> {
  return (await request<FoodDetail>(`GET /foods/{id}`.replace('{id}', String(id)))).data;
}

export async function getRestaurants(params: { q?: string; district?: string; foodId?: number; priceLevel?: number; sort?: string; page?: number; limit?: number } = {}): Promise<PageResult<Restaurant>> {
  const result = await request<Restaurant[]>('GET /restaurants' + queryString(params));
  return { items: result.data, meta: result.meta ?? { page: params.page ?? 1, limit: params.limit ?? 12, total: result.data.length } };
}

export async function getRestaurant(id: number): Promise<RestaurantDetail> {
  return (await request<RestaurantDetail>(`GET /restaurants/{id}`.replace('{id}', String(id)))).data;
}

export async function getReviews(id: number, page = 1): Promise<PageResult<Review>> {
  const result = await request<Review[]>(`GET /restaurants/{id}/reviews`.replace('{id}', String(id)) + queryString({ page, limit: 10 }));
  return { items: result.data, meta: result.meta ?? { page, limit: 10, total: result.data.length } };
}

export async function saveReview(id: number, input: { rating: number; comment: string }): Promise<Review> {
  return (await request<Review>(`POST /restaurants/{id}/reviews`.replace('{id}', String(id)), { method: 'POST', body: JSON.stringify(input) })).data;
}

export async function getFavorites(): Promise<FavoriteList> {
  return (await request<FavoriteList>('GET /favorites')).data;
}

export async function addFavorite(input: { targetType: 'FOOD' | 'RESTAURANT'; targetId: number }): Promise<void> {
  await request<null>('POST /favorites', { method: 'POST', body: JSON.stringify({ targetType: input.targetType, targetId: input.targetId }) });
}

export async function removeFavorite(targetType: 'FOOD' | 'RESTAURANT', targetId: number): Promise<void> {
  await request<null>(`DELETE /favorites/{targetType}/{targetId}`.replace('{targetType}', targetType).replace('{targetId}', String(targetId)), { method: 'DELETE' });
}

export async function generateItinerary(input: { date?: string; forceNew?: boolean } = {}): Promise<Itinerary> {
  return (await request<Itinerary>('POST /itinerary/generate', { method: 'POST', body: JSON.stringify(input) })).data;
}

export async function getItineraries(): Promise<Itinerary[]> {
  return (await request<Itinerary[]>('GET /itinerary')).data;
}

export async function getItinerary(id: number): Promise<Itinerary> {
  return (await request<Itinerary>(`GET /itinerary/{id}`.replace('{id}', String(id)))).data;
}

export async function getArticles(params: { page?: number; limit?: number } = {}): Promise<PageResult<Article>> {
  const result = await request<Article[]>('GET /articles' + queryString(params));
  return { items: result.data, meta: result.meta ?? { page: params.page ?? 1, limit: params.limit ?? 12, total: result.data.length } };
}

export async function getArticle(slug: string): Promise<Article> {
  return (await request<Article>(`GET /articles/{slug}`.replace('{slug}', encodeURIComponent(slug)))).data;
}

export async function getAdminStats(): Promise<AdminStats> {
  return (await request<AdminStats>('GET /admin/stats')).data;
}

export async function getAdminUsers(params: { q?: string; page?: number } = {}): Promise<PageResult<AdminUser>> {
  const result = await request<AdminUser[]>('GET /admin/users' + queryString({ ...params, limit: 12 }));
  return { items: result.data, meta: result.meta ?? { page: params.page ?? 1, limit: 12, total: result.data.length } };
}

export async function updateUserBan(id: number, input: { banned: boolean; reason?: string }): Promise<AdminUser> {
  return (await request<AdminUser>(`PATCH /admin/users/{id}/ban`.replace('{id}', String(id)), { method: 'PATCH', body: JSON.stringify(input) })).data;
}

export async function createRestaurant(input: RestaurantInput): Promise<Restaurant> {
  return (await request<Restaurant>('POST /admin/restaurants', { method: 'POST', body: JSON.stringify(input) })).data;
}

export async function updateRestaurant(id: number, input: RestaurantInput): Promise<Restaurant> {
  return (await request<Restaurant>(`PUT /admin/restaurants/{id}`.replace('{id}', String(id)), { method: 'PUT', body: JSON.stringify(input) })).data;
}

export async function deleteRestaurant(id: number): Promise<void> {
  await request<null>(`DELETE /admin/restaurants/{id}`.replace('{id}', String(id)), { method: 'DELETE' });
}

export async function createFood(input: FoodInput): Promise<Food> {
  return (await request<Food>('POST /admin/foods', { method: 'POST', body: JSON.stringify(input) })).data;
}

export async function updateFood(id: number, input: FoodInput): Promise<Food> {
  return (await request<Food>(`PUT /admin/foods/{id}`.replace('{id}', String(id)), { method: 'PUT', body: JSON.stringify(input) })).data;
}

export async function deleteFood(id: number): Promise<void> {
  await request<null>(`DELETE /admin/foods/{id}`.replace('{id}', String(id)), { method: 'DELETE' });
}

export async function createArticle(input: ArticleInput): Promise<Article> {
  return (await request<Article>('POST /admin/articles', { method: 'POST', body: JSON.stringify(input) })).data;
}

export async function updateArticle(id: number, input: ArticleInput): Promise<Article> {
  return (await request<Article>(`PUT /admin/articles/{id}`.replace('{id}', String(id)), { method: 'PUT', body: JSON.stringify(input) })).data;
}

export async function deleteArticle(id: number): Promise<void> {
  await request<null>(`DELETE /admin/articles/{id}`.replace('{id}', String(id)), { method: 'DELETE' });
}
