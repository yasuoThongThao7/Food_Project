import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { Link, NavLink, Navigate, Outlet, useLocation } from 'react-router-dom';
import { getToken } from '../api/http';
import type { Food, Restaurant, User } from '../api/types';
import { MapView, type MapMarker } from './MapView';
import { categoryLabel } from './helpers';

export function Navbar({ user, onLogout }: { user: User | null; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <header className="topbar">
      <Link to="/" className="brand" aria-label="Da Nang Food Guide trang chủ"><span className="brand-mark">🍜</span><span>Đà Nẵng<span className="brand-small">Food Guide</span></span></Link>
      <button className="mobile-menu" aria-label="Mở menu" aria-expanded={open} onClick={() => setOpen(!open)}>☰</button>
      <nav className={open ? 'nav-links nav-open' : 'nav-links'}>
        <NavLink to="/foods">Món ngon</NavLink><NavLink to="/restaurants">Quán ăn</NavLink><NavLink to="/articles">Cẩm nang</NavLink>
        {user && <NavLink to="/favorites">Đã lưu</NavLink>}
        {user?.role === 'ADMIN' && <NavLink to="/admin">Quản trị</NavLink>}
        {user ? <><Link to="/itinerary" className="nav-cta">Lộ trình của tôi</Link><button className="nav-logout" onClick={onLogout}>Đăng xuất</button></> : <Link to="/login" className="nav-cta">Đăng nhập</Link>}
      </nav>
    </header>
  );
}

export function AppLayout({ user, onLogout, children }: { user: User | null; onLogout: () => void; children?: ReactNode }) {
  return <><Navbar user={user} onLogout={onLogout} /><main className="main-shell">{children ?? <Outlet />}</main><footer className="footer">Một chút ngon lành, một vòng Đà Nẵng <span>♥</span></footer></>;
}

export function AuthGuard({ user, loading, children }: { user: User | null; loading: boolean; children: ReactNode }) {
  const location = useLocation();
  if (loading && getToken()) return <div className="route-loading"><div className="spinner" /><p>Đang kiểm tra tài khoản...</p></div>;
  if (!user && !getToken()) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

export function AdminGuard({ user, loading, children }: { user: User | null; loading: boolean; children: ReactNode }) {
  if (loading && getToken()) return <div className="route-loading"><div className="spinner" /><p>Đang kiểm tra quyền truy cập...</p></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== 'ADMIN') return <ForbiddenPage />;
  return <>{children}</>;
}

export function ForbiddenPage() {
  return <section className="center-state"><span className="state-icon">🔒</span><h1>Bạn chưa có quyền truy cập</h1><p>Tài khoản của bạn không có quyền quản trị trang này.</p><Link className="button primary" to="/">Về trang chủ</Link></section>;
}

export function NotFoundPage() {
  return <section className="center-state"><span className="state-icon">404</span><h1>Không tìm thấy trang</h1><p>Đường dẫn này không tồn tại trong Da Nang Food Guide.</p><Link className="button primary" to="/">Về trang chủ</Link></section>;
}

export function BannedPage({ reason }: { reason: string }) {
  return <section className="center-state"><span className="state-icon">⚠️</span><h1>Tài khoản đã bị khóa</h1><p>{reason}</p><Link className="button" to="/login">Đăng nhập tài khoản khác</Link></section>;
}

export function DataState({ loading, error, empty, retry, children }: { loading: boolean; error: Error | null; empty: boolean; retry: () => void; children: ReactNode }) {
  if (loading) return <div className="skeleton-grid" aria-label="Đang tải">{[0, 1, 2].map((item) => <div className="skeleton-card" key={item}><div className="skeleton-image" /><div className="skeleton-line" /><div className="skeleton-line short" /></div>)}</div>;
  if (error) return <div className="inline-state error-state" role="alert"><p>{error.message || 'Không thể tải dữ liệu.'}</p><button className="button small" onClick={retry}>Thử lại</button></div>;
  if (empty) return <div className="inline-state"><span className="state-icon">🍽️</span><p>Chưa có nội dung ở đây. Thử thay đổi bộ lọc nhé!</p></div>;
  return <>{children}</>;
}

export function StarRating({ rating, count, size = 'normal' }: { rating: number; count?: number; size?: 'normal' | 'small' }) {
  return <span className={`rating ${size}`} aria-label={`Đánh giá ${rating.toFixed(1)} trên 5`}><span aria-hidden="true">★</span> {rating.toFixed(1)} {count !== undefined && <span className="rating-count">({count})</span>}</span>;
}

export function FoodCard({ food, favorite = false, onFavorite }: { food: Food; favorite?: boolean; onFavorite?: (food: Food) => void }) {
  return <article className="food-card"><Link to={`/foods/${food.id}`}><img src={food.imageUrl || fallbackFood} alt={food.name} loading="lazy" /><div className="food-card-info"><span className="eyebrow">{categoryLabel(food.category)}</span><h3>{food.name}</h3><p>{food.description}</p></div></Link>{onFavorite && <button className={favorite ? 'heart active' : 'heart'} onClick={() => onFavorite(food)} aria-label={favorite ? `Bỏ lưu ${food.name}` : `Lưu ${food.name}`}>{favorite ? '♥' : '♡'}</button>}</article>;
}

const fallbackFood = 'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80';

export function RestaurantCard({ restaurant, onFavorite, favorite = false }: { restaurant: Restaurant; onFavorite?: (restaurant: Restaurant) => void; favorite?: boolean }) {
  return <article className="restaurant-card"><div className="restaurant-image"><Link to={`/restaurants/${restaurant.id}`}><img src={restaurant.imageUrl || fallbackFood} alt={restaurant.name} loading="lazy" /></Link>{onFavorite && <button className={favorite ? 'heart active' : 'heart'} onClick={() => onFavorite(restaurant)} aria-label={favorite ? `Bỏ lưu ${restaurant.name}` : `Lưu ${restaurant.name}`}>{favorite ? '♥' : '♡'}</button>}</div><div className="restaurant-info"><div className="restaurant-meta"><span>{restaurant.district}</span><StarRating rating={restaurant.ratingAvg} /></div><Link to={`/restaurants/${restaurant.id}`}><h3>{restaurant.name}</h3></Link><p>{restaurant.address}</p><div className="restaurant-bottom"><span className="price-level">{'₫'.repeat(restaurant.priceLevel)}</span><Link className="text-link" to={`/restaurants/${restaurant.id}`}>Xem chi tiết <span aria-hidden="true">→</span></Link></div></div></article>;
}

export function Pagination({ page, total, limit, onChange }: { page: number; total: number; limit: number; onChange: (page: number) => void }) {
  const pages = Math.ceil(total / limit);
  if (pages <= 1) return null;
  return <nav className="pagination" aria-label="Phân trang"><button disabled={page <= 1} onClick={() => onChange(page - 1)}>← Trước</button><span>Trang {page} / {pages}</span><button disabled={page >= pages} onClick={() => onChange(page + 1)}>Sau →</button></nav>;
}

export function ConfirmModal({ title, children, onCancel, onConfirm, confirmText = 'Xác nhận', danger = false }: { title: string; children: ReactNode; onCancel: () => void; onConfirm: () => void; confirmText?: string; danger?: boolean }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel(); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button className="modal-close" aria-label="Đóng" onClick={onCancel}>×</button><h2 id="modal-title">{title}</h2><div className="modal-content">{children}</div><div className="modal-actions"><button className="button" onClick={onCancel}>Hủy</button><button className={danger ? 'button danger' : 'button primary'} onClick={onConfirm}>{confirmText}</button></div></section></div>;
}

export function FavoriteButton({ targetType, targetId, initial = false, onToggle }: { targetType: 'FOOD' | 'RESTAURANT'; targetId: number; initial?: boolean; onToggle: (type: 'FOOD' | 'RESTAURANT', id: number, current: boolean) => void }) {
  return <button className={initial ? 'heart active' : 'heart'} aria-label={initial ? 'Bỏ khỏi yêu thích' : 'Thêm vào yêu thích'} onClick={() => onToggle(targetType, targetId, initial)}>{initial ? '♥' : '♡'}</button>;
}

export function MapLink({ restaurant }: { restaurant: Pick<Restaurant, 'lat' | 'lng'> }) {
  return <a className="button small" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/directions?to=${restaurant.lat},${restaurant.lng}`}>Chỉ đường</a>;
}

export function SearchBox({ value, onChange, placeholder = 'Tìm kiếm...' }: { value: string; onChange: (value: string) => void; placeholder?: string }) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  useEffect(() => {
    const timer = window.setTimeout(() => onChange(local), 400);
    return () => window.clearTimeout(timer);
  }, [local, onChange]);
  return <label className="search-box"><span aria-hidden="true">⌕</span><span className="sr-only">Tìm kiếm</span><input value={local} onChange={(event) => setLocal(event.target.value)} placeholder={placeholder} /></label>;
}

export function PageHeading({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="page-heading"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</div>;
}

export function FormField({ label, children }: { label: string; children: ReactNode }) {
  return <label className="form-field"><span>{label}</span>{children}</label>;
}

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return <section className="auth-page"><div className="auth-art"><span>🥢</span><h2>Mỗi món ngon<br />là một câu chuyện.</h2><p>Khám phá Đà Nẵng qua từng hương vị.</p></div><div className="auth-form-wrap"><Link className="back-link" to="/">← Trang chủ</Link><h1>{title}</h1><p>{subtitle}</p>{children}</div></section>;
}

export function FormMessage({ message }: { message: string }) {
  return message ? <p className="form-error" role="alert">{message}</p> : null;
}

export function Form({ onSubmit, children }: { onSubmit: (event: FormEvent<HTMLFormElement>) => void; children: ReactNode }) {
  return <form className="form-stack" onSubmit={onSubmit}>{children}</form>;
}

export function MapPanel({ markers, polyline }: { markers: MapMarker[]; polyline?: boolean }) {
  return <MapView markers={markers} polyline={polyline} />;
}
