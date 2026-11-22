import { Suspense, lazy, useEffect, useState } from 'react';
import { Route, Routes, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { clearToken, getToken } from './api/http';
import { getMe } from './api/endpoints';
import { queryKeys } from './api/queryKeys';
import type { User } from './api/types';
import { AdminGuard, AppLayout, AuthGuard, BannedPage, NotFoundPage } from './components/Shared';

const Home = lazy(() => import('./pages/PublicPages').then((module) => ({ default: module.HomePage })));
const SearchPage = lazy(() => import('./pages/PublicPages').then((module) => ({ default: module.SearchPage })));
const FoodList = lazy(() => import('./pages/PublicPages').then((module) => ({ default: module.FoodListPage })));
const FoodDetail = lazy(() => import('./pages/PublicPages').then((module) => ({ default: module.FoodDetailPage })));
const RestaurantList = lazy(() => import('./pages/PublicPages').then((module) => ({ default: module.RestaurantListPage })));
const RestaurantDetail = lazy(() => import('./pages/PublicPages').then((module) => ({ default: module.RestaurantDetailPage })));
const ArticleList = lazy(() => import('./pages/PublicPages').then((module) => ({ default: module.ArticleListPage })));
const ArticleDetail = lazy(() => import('./pages/PublicPages').then((module) => ({ default: module.ArticleDetailPage })));
const Login = lazy(() => import('./pages/AccountPages').then((module) => ({ default: module.LoginPage })));
const Register = lazy(() => import('./pages/AccountPages').then((module) => ({ default: module.RegisterPage })));
const Favorites = lazy(() => import('./pages/AccountPages').then((module) => ({ default: module.FavoritesPage })));
const Itinerary = lazy(() => import('./pages/AccountPages').then((module) => ({ default: module.ItineraryPage })));
const AdminPage = lazy(() => import('./pages/AdminPage'));

function RouteLoading() {
  return <div className="route-loading"><div className="spinner" /><p>Đang chuẩn bị món ngon...</p></div>;
}

export default function App() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [bannedReason, setBannedReason] = useState('');
  const { data: user, isLoading: userLoading } = useQuery<User>({
    queryKey: queryKeys.me,
    queryFn: getMe,
    enabled: Boolean(getToken()),
    retry: false
  });

  useEffect(() => {
    const banned = (event: Event) => setBannedReason((event as CustomEvent<string>).detail);
    const logout = () => { queryClient.clear(); navigate('/login'); };
    window.addEventListener('dnfg:banned', banned);
    window.addEventListener('dnfg:logout', logout);
    return () => {
      window.removeEventListener('dnfg:banned', banned);
      window.removeEventListener('dnfg:logout', logout);
    };
  }, [navigate, queryClient]);

  const logout = () => {
    clearToken();
    queryClient.clear();
    navigate('/login');
  };

  if (bannedReason) return <BannedPage reason={bannedReason} />;
  return <AppLayout user={user ?? null} onLogout={logout}>
    <Suspense fallback={<RouteLoading />}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/foods" element={<FoodList />} />
        <Route path="/foods/:id" element={<FoodDetail />} />
        <Route path="/restaurants" element={<RestaurantList />} />
        <Route path="/restaurants/:id" element={<RestaurantDetail />} />
        <Route path="/articles" element={<ArticleList />} />
        <Route path="/articles/:slug" element={<ArticleDetail />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/favorites" element={<AuthGuard user={user ?? null} loading={userLoading}><Favorites /></AuthGuard>} />
        <Route path="/itinerary" element={<AuthGuard user={user ?? null} loading={userLoading}><Itinerary /></AuthGuard>} />
        <Route path="/admin" element={<AdminGuard user={user ?? null} loading={userLoading}><AdminPage /></AdminGuard>} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  </AppLayout>;
}
