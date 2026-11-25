export const queryKeys = {
  me: ['me'] as const,
  foods: (filters?: object) => ['foods', filters] as const,
  food: (id: number) => ['food', id] as const,
  restaurants: (filters?: object) => ['restaurants', filters] as const,
  restaurant: (id: number) => ['restaurant', id] as const,
  reviews: (id: number, page: number) => ['reviews', id, page] as const,
  favorites: ['favorites'] as const,
  history: ['search-history'] as const,
  predictionFoods: (labels: string[]) => ['prediction-foods', labels] as const,
  itineraries: ['itineraries'] as const,
  itinerary: (id: number) => ['itinerary', id] as const,
  articles: (page?: number) => ['articles', page] as const,
  article: (slug: string) => ['article', slug] as const,
  adminStats: ['admin-stats'] as const,
  adminUsers: (q: string, page: number) => ['admin-users', q, page] as const
};
