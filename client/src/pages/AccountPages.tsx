import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  clearSearchHistory, generateItinerary, getFavorites, getItineraries,
  getItinerary, getSearchHistory, login, register, removeFavorite
} from '../api/endpoints';
import { ApiError, saveToken } from '../api/http';
import { queryKeys } from '../api/queryKeys';
import type { Itinerary, ItineraryStop } from '../api/types';
import {
  AuthLayout, DataState, Form, FormField, FormMessage, MapPanel, PageHeading,
  RestaurantCard, StarRating
} from '../components/Shared';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const client = useQueryClient();
  const state = location.state;
  const redirectTo = state && typeof state === 'object' && 'from' in state && typeof state.from === 'string' ? state.from : '/';
  const itineraryPrompt = redirectTo === '/itinerary';
  const [message, setMessage] = useState('');
  const mutation = useMutation({
    mutationFn: login,
    onSuccess: ({ token, user }) => {
      saveToken(token);
      client.setQueryData(queryKeys.me, user);
      navigate(redirectTo, { replace: true });
    }
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setMessage('');
    mutation.mutate({ email: String(form.get('email')), password: String(form.get('password')) });
  };
  return <AuthLayout title="Chào mừng bạn trở lại" subtitle={itineraryPrompt ? 'Đăng nhập để tạo lộ trình ẩm thực dành riêng cho bạn.' : 'Đăng nhập để lưu lại những khám phá ngon lành.'}><Form onSubmit={submit}><FormField label="Email"><input name="email" type="email" autoComplete="email" placeholder="ban@email.com" required /></FormField><FormField label="Mật khẩu"><input name="password" type="password" autoComplete="current-password" placeholder="Nhập mật khẩu" required /></FormField><FormMessage message={message || mutation.error?.message || ''} /><button className="button primary full-button" disabled={mutation.isPending}>{mutation.isPending ? 'Đang đăng nhập...' : 'Đăng nhập'}</button></Form><p className="auth-switch">Chưa có tài khoản? <Link to="/register">Đăng ký miễn phí</Link></p></AuthLayout>;
}

export function RegisterPage() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: register,
    onSuccess: ({ token, user }) => {
      saveToken(token);
      client.setQueryData(queryKeys.me, user);
      navigate('/', { replace: true });
    }
  });
  const [passwordError, setPasswordError] = useState('');
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = String(form.get('password'));
    if (password.length < 8) { setPasswordError('Mật khẩu cần có ít nhất 8 ký tự.'); return; }
    setPasswordError('');
    mutation.mutate({ email: String(form.get('email')), name: String(form.get('name')), password });
  };
  return <AuthLayout title="Tạo tài khoản mới" subtitle="Bắt đầu hành trình khám phá ẩm thực Đà Nẵng."><Form onSubmit={submit}><FormField label="Tên của bạn"><input name="name" autoComplete="name" placeholder="Nguyễn An" required /></FormField><FormField label="Email"><input name="email" type="email" autoComplete="email" placeholder="ban@email.com" required /></FormField><FormField label="Mật khẩu"><input name="password" type="password" autoComplete="new-password" placeholder="Ít nhất 8 ký tự" minLength={8} required /></FormField><FormMessage message={passwordError || mutation.error?.message || ''} /><button className="button primary full-button" disabled={mutation.isPending}>{mutation.isPending ? 'Đang tạo tài khoản...' : 'Tạo tài khoản'}</button></Form><p className="auth-switch">Đã có tài khoản? <Link to="/login">Đăng nhập</Link></p></AuthLayout>;
}

export function FavoritesPage() {
  const [tab, setTab] = useState<'foods' | 'restaurants' | 'history'>('foods');
  const client = useQueryClient();
  const favorites = useQuery({ queryKey: queryKeys.favorites, queryFn: getFavorites });
  const history = useQuery({ queryKey: queryKeys.history, queryFn: getSearchHistory, enabled: tab === 'history' });
  const clear = useMutation({ mutationFn: clearSearchHistory, onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.history }) });
  const remove = useMutation({
    mutationFn: ({ type, id }: { type: 'FOOD' | 'RESTAURANT'; id: number }) => removeFavorite(type, id),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.favorites })
  });
  return <div className="content-page"><PageHeading eyebrow="Dành riêng cho bạn" title="Món ngon đã lưu" description="Những điều bạn muốn quay lại khám phá." /><div className="tabs"><button className={tab === 'foods' ? 'tab active' : 'tab'} onClick={() => setTab('foods')}>Món yêu thích</button><button className={tab === 'restaurants' ? 'tab active' : 'tab'} onClick={() => setTab('restaurants')}>Quán yêu thích</button><button className={tab === 'history' ? 'tab active' : 'tab'} onClick={() => setTab('history')}>Lịch sử tìm kiếm</button></div>
    {remove.error && <p className="form-error" role="alert">{remove.error.message}</p>}
    {tab === 'foods' && <DataState loading={favorites.isLoading} error={favorites.error} empty={!favorites.data?.foods.length} retry={() => void favorites.refetch()}><div className="food-grid">{favorites.data?.foods.map((food) => <div className="favorite-card" key={food.id}><FoodLink food={food} /><button className="heart active" aria-label={`Bỏ lưu ${food.name}`} onClick={() => remove.mutate({ type: 'FOOD', id: food.id })}>♥</button></div>)}</div></DataState>}
    {tab === 'restaurants' && <DataState loading={favorites.isLoading} error={favorites.error} empty={!favorites.data?.restaurants.length} retry={() => void favorites.refetch()}><div className="restaurant-grid">{favorites.data?.restaurants.map((restaurant) => <div key={restaurant.id} className="favorite-restaurant"><RestaurantCard restaurant={restaurant} /><button className="heart active" aria-label={`Bỏ lưu ${restaurant.name}`} onClick={() => remove.mutate({ type: 'RESTAURANT', id: restaurant.id })}>♥</button></div>)}</div></DataState>}
    {tab === 'history' && <><div className="history-actions"><span>Lần tìm kiếm gần đây</span><button className="text-button" disabled={clear.isPending || !history.data?.length} onClick={() => clear.mutate()}>Xóa lịch sử</button></div>{clear.error && <p className="form-error" role="alert">{clear.error.message}</p>}<DataState loading={history.isLoading} error={history.error} empty={!history.data?.length} retry={() => void history.refetch()}><div className="history-list">{history.data?.map((entry) => <div className="history-row" key={entry.id}><span className="history-thumb">🍜</span><span><strong>{entry.foods.map((food) => food.name).join(', ') || 'Món ăn chưa nhận diện'}</strong><small>{new Date(entry.createdAt).toLocaleString('vi-VN')}</small></span></div>)}</div></DataState></>}
  </div>;
}

function FoodLink({ food }: { food: { id: number; name: string; imageUrl: string } }) {
  return <Link className="food-card" to={`/foods/${food.id}`}><img src={food.imageUrl} alt={food.name} /><div className="food-card-info"><h3>{food.name}</h3></div></Link>;
}

const slots: Record<ItineraryStop['slot'], { label: string; time: string; emoji: string }> = {
  breakfast: { label: 'Sáng', time: '06:00 – 09:00', emoji: '🌤️' },
  lunch: { label: 'Trưa', time: '11:00 – 13:00', emoji: '☀️' },
  snack: { label: 'Xế', time: '15:00 – 17:00', emoji: '🍵' },
  dinner: { label: 'Tối', time: '18:00 – 21:00', emoji: '🌙' }
};
const slotOrder: ItineraryStop['slot'][] = ['breakfast', 'lunch', 'snack', 'dinner'];

export function ItineraryPage() {
  const client = useQueryClient();
  const [activeId, setActiveId] = useState<number | null>(null);
  const [generated, setGenerated] = useState<Itinerary | null>(null);
  const [progress, setProgress] = useState(0);
  const [generationNotice, setGenerationNotice] = useState('');
  const history = useQuery({ queryKey: queryKeys.itineraries, queryFn: getItineraries });
  const favorites = useQuery({ queryKey: queryKeys.favorites, queryFn: getFavorites });
  const searchHistory = useQuery({ queryKey: queryKeys.history, queryFn: getSearchHistory });
  const selected = useQuery({
    queryKey: queryKeys.itinerary(activeId ?? 0),
    queryFn: () => getItinerary(activeId ?? 0),
    enabled: activeId !== null && activeId !== generated?.id
  });
  const generate = useMutation({
    mutationFn: generateItinerary,
    onMutate: () => setProgress(0),
    onSuccess: (itinerary, input) => {
      setGenerated(itinerary);
      setActiveId(itinerary.id);
      setGenerationNotice(input?.forceNew
        ? itinerary.source === 'AI'
          ? 'Đã tạo lộ trình mới bằng AI.'
          : 'Đã tạo lộ trình mới theo đánh giá.'
        : '');
      void client.invalidateQueries({ queryKey: queryKeys.itineraries });
    }
  });
  useEffect(() => {
    if (!generate.isPending) return;
    const timer = window.setInterval(() => setProgress((current) => Math.min(current + 1, 15)), 1000);
    return () => window.clearInterval(timer);
  }, [generate.isPending]);
  const itinerary = generated?.id === activeId ? generated : selected.data;
  const sortedPlan = useMemo(() => itinerary?.plan.slice().sort((a, b) => slotOrder.indexOf(a.slot) - slotOrder.indexOf(b.slot)) ?? [], [itinerary]);
  const markers = useMemo(() => sortedPlan.map((stop, index) => ({
    lat: stop.restaurant.lat, lng: stop.restaurant.lng, label: stop.restaurant.name,
    address: stop.restaurant.address, order: index + 1
  })), [sortedPlan]);
  const noPreferences = !favorites.data?.foods.length && !favorites.data?.restaurants.length && !searchHistory.data?.length;
  const create = (forceNew = false) => {
    setGenerated(null);
    setActiveId(null);
    setGenerationNotice('');
    generate.mutate(forceNew ? { forceNew: true } : {});
  };
  return <div className="content-page"><PageHeading eyebrow="Lịch trình ẩm thực" title="Một ngày ăn ngon ở Đà Nẵng" description="Lộ trình riêng với những món ngon và quán ăn địa phương." action={<button className="button primary" onClick={() => create(Boolean(itinerary))} disabled={generate.isPending}>{generate.isPending ? 'Đang tạo...' : itinerary ? '↻ Tạo lại' : '✦ Tạo lộ trình hôm nay'}</button>} />
    {noPreferences && <div className="hint-banner"><span>💡</span><p>Thêm món yêu thích, đánh giá quán hoặc tìm món bằng ảnh để gợi ý ngày càng hợp gu hơn nhé.</p></div>}
    {generate.isPending && <div className="generating-card"><div className="spinner" /><div><strong>Đang chuẩn bị hành trình ngon lành...</strong><p>Chúng mình đang chọn quán, cân đối thời gian và sắp xếp lộ trình. Thường mất khoảng 15 giây.</p><div className="progress-track"><span style={{ width: `${Math.min(progress / 15 * 100, 95)}%` }} /></div></div></div>}
    {generate.error && <div className="inline-state error-state" role="alert"><p>{generate.error instanceof ApiError && generate.error.status === 429 ? 'Bạn tạo quá nhiều, thử lại sau nhé.' : generate.error.message}</p><button className="button small" onClick={() => create(Boolean(itinerary))}>Thử lại</button></div>}
    {generationNotice && <p className="inline-state" role="status">{generationNotice}</p>}
    {itinerary && <><div className="itinerary-date"><span>{new Date(`${itinerary.date}T00:00:00`).toLocaleDateString('vi-VN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</span></div><div className="itinerary-layout"><div className="timeline">{sortedPlan.map((stop, index) => <StopCard key={`${stop.slot}-${stop.restaurant.id}`} stop={stop} order={index + 1} fallback={itinerary.source === 'FALLBACK'} />)}</div>{markers.length > 0 && <div className="itinerary-map"><MapPanel markers={markers} polyline /><p>Hành trình các quán theo thứ tự ghé thăm</p></div>}</div></>}
    {!itinerary && !generate.isPending && !generate.error && <div className="itinerary-intro"><div className="itinerary-illustration">🗺️</div><h2>Sẵn sàng cho một ngày thật ngon?</h2><p>Để chúng mình chọn món ngon, quán thú vị và nối thành một hành trình vừa vặn.</p><button className="button primary" onClick={() => create()}>Tạo lộ trình hôm nay ✦</button></div>}
    <section className="previous-trips"><div className="section-title"><div><span className="eyebrow">Những chuyến đi trước</span><h2>Lộ trình đã tạo</h2></div></div><DataState loading={history.isLoading} error={history.error} empty={!history.data?.length} retry={() => void history.refetch()}><div className="trip-list">{history.data?.map((trip) => <button key={trip.id} className={activeId === trip.id ? 'trip-item active' : 'trip-item'} onClick={() => { setGenerated(null); setActiveId(trip.id); }}><span className="trip-emoji">🍜</span><span><strong>{new Date(`${trip.date}T00:00:00`).toLocaleDateString('vi-VN', { day: 'numeric', month: 'long' })}</strong><small>{trip.plan.length} điểm dừng · {trip.source === 'FALLBACK' ? 'Gợi ý theo đánh giá' : 'Gợi ý AI'}</small></span><span>→</span></button>)}</div></DataState></section>
  </div>;
}

function StopCard({ stop, order, fallback }: { stop: ItineraryStop; order: number; fallback: boolean }) {
  const slot = slots[stop.slot];
  return <article className="stop-card"><div className="stop-marker">{order}</div><div className="stop-content"><div className="stop-header"><span>{slot.emoji} {slot.label}</span><small>{slot.time}</small></div>{fallback && <span className="fallback-badge">Gợi ý theo đánh giá</span>}<Link to={`/restaurants/${stop.restaurant.id}`} className="stop-restaurant"><img src={stop.restaurant.imageUrl} alt={stop.restaurant.name} /><span><strong>{stop.restaurant.name}</strong><small>{stop.restaurant.address}</small></span><span className="stop-arrow">↗</span></Link><div className="stop-details">{stop.food && <span>🍲 {stop.food.name}</span>}<span>{'₫'.repeat(stop.restaurant.priceLevel)}</span><StarRating rating={stop.restaurant.ratingAvg} size="small" /></div><p className="stop-reason">“{stop.reason}”</p><a className="text-link" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/directions?to=${stop.restaurant.lat},${stop.restaurant.lng}`}>Chỉ đường →</a></div></article>;
}
