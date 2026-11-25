import { useEffect, useMemo, useRef, useState, type DragEvent, type FormEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import {
  getArticles, getArticle, getFavorites, getFood, getFoods, getRestaurant, getRestaurants,
  getReviews, removeFavorite, addFavorite, saveReview, predictImage, getSearchHistory, clearSearchHistory
} from '../api/endpoints';
import { ApiError } from '../api/http';
import { queryKeys } from '../api/queryKeys';
import type { Food, Restaurant } from '../api/types';
import {
  DataState, FoodCard, MapPanel, PageHeading, Pagination,
  RestaurantCard, SearchBox, StarRating
} from '../components/Shared';
import { categoryLabel } from '../components/helpers';

const categories = [
  ['noodle', 'Món nước'], ['seafood', 'Hải sản'], ['snack', 'Ăn vặt'],
  ['dessert', 'Tráng miệng'], ['drink', 'Đồ uống'], ['other', 'Đặc sản']
];

function normalizeAiLabel(label: string): string {
  return label.toLowerCase().replace(/[-\s]/g, '_');
}

export function HomePage() {
  const foods = useQuery({ queryKey: queryKeys.foods({ page: 1 }), queryFn: () => getFoods({ page: 1, limit: 4 }) });
  const restaurants = useQuery({ queryKey: queryKeys.restaurants({ sort: 'rating', page: 1 }), queryFn: () => getRestaurants({ sort: 'rating', page: 1, limit: 4 }) });
  const articles = useQuery({ queryKey: queryKeys.articles(1), queryFn: () => getArticles({ page: 1, limit: 3 }) });
  return <div className="home-page">
    <section className="hero"><div className="hero-copy"><span className="eyebrow">Ăn ngon như người Đà Nẵng</span><h1>Đi một vòng,<br /><em>thương một món.</em></h1><p>Tìm hương vị địa phương, quán ăn được yêu thích và hành trình ngon lành dành riêng cho bạn.</p><div className="hero-actions"><Link className="button primary" to="/search"><span>✦</span> Tìm món bằng ảnh</Link><Link className="button outline-light" to="/itinerary">Lộ trình hôm nay <span>→</span></Link></div><div className="hero-note"><span>✺</span> Gợi ý ngon lành, khám phá dễ dàng</div></div><div className="hero-visual"><img src="https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=1100&q=85" alt="Mâm đồ ăn Việt Nam đầy màu sắc" /><div className="hero-sticker"><span>Đà Nẵng</span><strong>ngon mê ly!</strong></div><div className="hero-image-caption">Hương vị miền Trung · Đậm đà khó quên</div></div></section>
    <section className="section"><SectionTitle eyebrow="Đặc sản địa phương" title="Món ngon nên thử" link="/foods" /><DataState loading={foods.isLoading} error={foods.error} empty={!foods.data?.items.length} retry={() => void foods.refetch()}><div className="food-grid">{foods.data?.items.map((food) => <FoodCard key={food.id} food={food} />)}</div></DataState></section>
    <section className="section section-tint"><SectionTitle eyebrow="Được yêu thích" title="Quán ăn nổi bật" link="/restaurants?sort=rating" /><DataState loading={restaurants.isLoading} error={restaurants.error} empty={!restaurants.data?.items.length} retry={() => void restaurants.refetch()}><div className="restaurant-grid">{restaurants.data?.items.map((restaurant) => <RestaurantCard key={restaurant.id} restaurant={restaurant} />)}</div></DataState></section>
    <section className="section"><SectionTitle eyebrow="Chuyện ăn uống" title="Góc Đà Nẵng" link="/articles" /><DataState loading={articles.isLoading} error={articles.error} empty={!articles.data?.items.length} retry={() => void articles.refetch()}><div className="article-grid">{articles.data?.items.map((article, index) => <Link className="article-card" to={`/articles/${article.slug}`} key={article.id}><img src={article.coverUrl || `https://images.unsplash.com/photo-${index % 2 ? '1504674900247-0877df9cc836' : '1555939594-58d7cb561ad1'}?auto=format&fit=crop&w=850&q=80`} alt={article.title} loading="lazy" /><div><span className="eyebrow">Cẩm nang Đà Nẵng</span><h3>{article.title}</h3><p>{article.summary}</p><span className="text-link">Đọc bài viết →</span></div></Link>)}</div></DataState></section>
  </div>;
}

function SectionTitle({ eyebrow, title, link }: { eyebrow: string; title: string; link: string }) {
  return <div className="section-title"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div><Link to={link} className="text-link">Xem tất cả <span>→</span></Link></div>;
}

async function resizeImage(file: File): Promise<Blob> {
  const image = await createImageBitmap(file);
  const scale = Math.min(1, 1024 / Math.max(image.width, image.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(image.width * scale));
  canvas.height = Math.max(1, Math.round(image.height * scale));
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Trình duyệt không thể xử lý ảnh này.');
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  image.close();
  return new Promise((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('Không thể chuyển đổi ảnh.')), 'image/jpeg', 0.8));
}

export function SearchPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [fileError, setFileError] = useState('');
  const [selected, setSelected] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const history = useQuery({ queryKey: queryKeys.history, queryFn: getSearchHistory, enabled: Boolean(localStorage.getItem('dnfg_token')) });
  const favorites = useQuery({ queryKey: queryKeys.favorites, queryFn: getFavorites, enabled: Boolean(localStorage.getItem('dnfg_token')) });
  const clearHistory = useMutation({
    mutationFn: clearSearchHistory,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.history })
  });
  const search = useMutation({
    mutationFn: async (image: File) => predictImage(await resizeImage(image)),
    onSuccess: (result) => {
      setSelected(result.dishes[0]?.order ?? null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.history });
    }
  });
  const detectedLabels = search.data?.dishes.map((dish) => dish.class_name) ?? [];
  const foodCatalog = useQuery({
    queryKey: queryKeys.predictionFoods(detectedLabels),
    queryFn: () => getFoods({ page: 1, limit: 50 }),
    enabled: Boolean(search.data?.success && detectedLabels.length)
  });
  const chosen = search.data?.dishes.find((dish) => dish.order === selected);
  const chosenFood = chosen && foodCatalog.data?.items.find((food) => normalizeAiLabel(food.aiLabel) === normalizeAiLabel(chosen.class_name));
  const chosenFoodDetail = useQuery({
    queryKey: queryKeys.food(chosenFood?.id ?? 0),
    queryFn: () => {
      if (!chosenFood) throw new Error('Không tìm thấy món ăn trong danh mục.');
      return getFood(chosenFood.id);
    },
    enabled: Boolean(chosenFood)
  });
  const savedIds = new Set(favorites.data?.restaurants.map((restaurant) => restaurant.id) ?? []);
  const favoriteMutation = useMutation({
    mutationFn: (restaurant: Restaurant) => savedIds.has(restaurant.id)
      ? removeFavorite('RESTAURANT', restaurant.id)
      : addFavorite({ targetType: 'RESTAURANT', targetId: restaurant.id }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: queryKeys.favorites }); }
  });
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const setImage = (image: File | undefined) => {
    if (!image) return;
    if (!image.type.startsWith('image/')) { setFileError('Vui lòng chọn tệp hình ảnh.'); return; }
    if (image.size > 10 * 1024 * 1024) { setFileError('Ảnh phải có dung lượng tối đa 10 MB.'); return; }
    setFileError('');
    setFile(image);
    setPreview(URL.createObjectURL(image));
    search.reset();
  };
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    setImage(event.dataTransfer.files[0]);
  };

  return <div className="content-page"><PageHeading eyebrow="Khám phá bằng AI" title="Món này tên gì nhỉ?" description="Tải ảnh món ăn lên, để chúng mình tìm đúng hương vị và quán ngon gần bạn." />
    <div className="search-layout">
      <div className="search-main">
        <div className={`upload-box ${dragging ? 'dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
          {preview ? <div className="upload-preview"><div className="prediction-image"><img src={preview} alt="Ảnh món ăn đã chọn" />{search.data?.dishes.map((dish) => <div key={dish.order} className="prediction-box" style={{ left: `${dish.box_percent.left}%`, top: `${dish.box_percent.top}%`, width: `${dish.box_percent.width}%`, height: `${dish.box_percent.height}%`, borderColor: dish.color }}><span style={{ backgroundColor: dish.color }}>{dish.class_name} · {dish.confidence}%</span></div>)}</div><button className="remove-image" onClick={() => { setPreview(''); setFile(null); search.reset(); }}>Đổi ảnh</button></div> : <><div className="upload-icon">📸</div><h2>Chọn ảnh món ăn</h2><p>Kéo thả ảnh vào đây hoặc chụp ảnh trực tiếp</p><div className="upload-buttons"><button className="button primary" onClick={() => inputRef.current?.click()}>Chọn ảnh từ thiết bị</button><button className="button" onClick={() => { if (inputRef.current) { inputRef.current.setAttribute('capture', 'environment'); inputRef.current.click(); } }}>Chụp ảnh</button></div><span className="upload-caption">JPG, PNG hoặc WebP · tối đa 10 MB</span></>}
          <input ref={inputRef} className="sr-only" type="file" accept="image/*" capture="environment" aria-label="Chọn hoặc chụp ảnh món ăn" onChange={(event) => setImage(event.target.files?.[0])} />
        </div>
        {fileError && <p className="form-error" role="alert">{fileError}</p>}
        {file && <button className="button primary search-submit" disabled={search.isPending} onClick={() => search.mutate(file)}>{search.isPending ? 'Đang nhận diện món ăn...' : 'Tìm món ăn ✦'}</button>}
        {search.isPending && <div className="ai-progress"><div className="spinner" /><span>Đang tìm hương vị trong ảnh của bạn...</span></div>}
        {search.error && <div role="alert" className="inline-state error-state"><p>{search.error instanceof ApiError && search.error.code === 'AI_UNAVAILABLE' ? 'AI đang bận, thử lại nhé.' : search.error.message}</p><button className="button small" onClick={() => file && search.mutate(file)}>Thử lại</button></div>}
        {favoriteMutation.error && <p className="form-error" role="alert">{favoriteMutation.error.message}</p>}
        {search.data && <section className="results-section"><div className="result-heading"><div><span className="eyebrow">Kết quả nhận diện</span><h2>{search.data.message}</h2></div></div>
          {!search.data.success || search.data.require_retake ? <div className="inline-state"><span className="state-icon">🧐</span><h3>Chưa nhận ra món ăn này</h3><p>{search.data.message}</p></div> : <>
            <div className="detected-chips">{search.data.dishes.map((dish) => {
              const food = foodCatalog.data?.items.find((item) => normalizeAiLabel(item.aiLabel) === normalizeAiLabel(dish.class_name));
              return <button key={dish.order} className={selected === dish.order ? 'detected-chip active' : 'detected-chip'} onClick={() => setSelected(dish.order)}><span>{food?.name ?? dish.class_name.replaceAll('_', ' ')}</span><small>{dish.confidence}%</small></button>;
            })}</div>
            {foodCatalog.data && search.data.dishes.some((dish) => !foodCatalog.data?.items.some((food) => normalizeAiLabel(food.aiLabel) === normalizeAiLabel(dish.class_name))) && <p className="unmatched-note">Một số món AI nhận diện chưa có trong danh mục món ăn.</p>}
            {chosen && <div className="instant-results"><div className="result-heading"><div><span className="eyebrow">Kết quả nhận diện</span><h2>{chosenFood?.name ?? chosen.class_name.replaceAll('_', ' ')}</h2></div>{chosenFood && <Link className="text-link" to={`/restaurants?foodId=${chosenFood.id}`}>Xem tất cả quán →</Link>}</div>
              {foodCatalog.isLoading || chosenFoodDetail.isLoading ? <div className="ai-progress"><div className="spinner" /><span>Đang tìm quán bán món này...</span></div> : foodCatalog.error ? <p className="form-error" role="alert">{foodCatalog.error.message}</p> : chosenFoodDetail.error ? <p className="form-error" role="alert">{chosenFoodDetail.error.message}</p> : chosenFoodDetail.data?.restaurants.length ? <div className="restaurant-grid">{chosenFoodDetail.data.restaurants.map((restaurant) => <RestaurantCard key={restaurant.id} restaurant={restaurant} favorite={savedIds.has(restaurant.id)} onFavorite={(item) => { if (!localStorage.getItem('dnfg_token')) { navigate('/login'); return; } favoriteMutation.mutate(item); }} />)}</div> : <div className="inline-state"><p>{chosenFood ? 'Chưa tìm thấy quán phù hợp với món này.' : 'Món AI nhận diện chưa có trong danh mục.'}</p></div>}
            </div>}
          </>}
        </section>}
      </div>
      <aside className="history-panel"><div className="history-title"><h2>Lịch sử tìm kiếm</h2><span>⏱</span></div>{localStorage.getItem('dnfg_token') ? <><button className="text-button history-clear" disabled={clearHistory.isPending || !history.data?.length} onClick={() => clearHistory.mutate()}>Xóa lịch sử</button>{clearHistory.error && <p className="form-error" role="alert">{clearHistory.error.message}</p>}<DataState loading={history.isLoading} error={history.error} empty={!history.data?.length} retry={() => void history.refetch()}>{history.data?.map((entry) => <div className="history-item" key={entry.id}><span className="history-thumb">🍜</span><span><strong>{entry.foods.map((food) => food.name).join(', ') || 'Ảnh món ăn'}</strong><small>{new Date(entry.createdAt).toLocaleDateString('vi-VN')}</small></span></div>)}</DataState></> : <div className="history-login"><span>🔐</span><p>Đăng nhập để xem lại những món bạn đã tìm.</p><Link className="text-link" to="/login">Đăng nhập ngay →</Link></div>}</aside>
    </div>
  </div>;
}

export function FoodListPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const category = params.get('category') ?? '';
  const page = Number(params.get('page') ?? '1');
  const [search, setSearch] = useState(q);
  const filters = useMemo(() => ({ q, category, page, limit: 12 }), [q, category, page]);
  const query = useQuery({ queryKey: queryKeys.foods(filters), queryFn: () => getFoods(filters) });
  const favorites = useQuery({ queryKey: queryKeys.favorites, queryFn: getFavorites, enabled: Boolean(localStorage.getItem('dnfg_token')) });
  const client = useQueryClient();
  const navigate = useNavigate();
  const favoriteMutation = useMutation({
    mutationFn: ({ food, favorite }: { food: Food; favorite: boolean }) => favorite
      ? removeFavorite('FOOD', food.id)
      : addFavorite({ targetType: 'FOOD', targetId: food.id }),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.favorites })
  });
  const savedIds = new Set(favorites.data?.foods.map((food) => food.id) ?? []);
  const update = (key: string, value: string) => setParams((current) => { const next = new URLSearchParams(current); if (value) next.set(key, value); else next.delete(key); next.delete('page'); return next; });
  return <div className="content-page"><PageHeading eyebrow="Hương vị Đà Nẵng" title="Món ngon địa phương" description="Từ tô mì Quảng đậm đà đến món ăn vặt thân quen." />
    <div className="filter-bar"><SearchBox value={search} onChange={(value) => { setSearch(value); update('q', value); }} placeholder="Tìm món ăn..." /><div className="category-pills"><button className={!category ? 'pill active' : 'pill'} onClick={() => update('category', '')}>Tất cả</button>{categories.map(([id, name]) => <button key={id} className={category === id ? 'pill active' : 'pill'} onClick={() => update('category', id)}>{name}</button>)}</div></div>
    {favoriteMutation.error && <p className="form-error" role="alert">{favoriteMutation.error.message}</p>}<DataState loading={query.isLoading} error={query.error} empty={!query.data?.items.length} retry={() => void query.refetch()}><div className="food-grid">{query.data?.items.map((food) => <FoodCard key={food.id} food={food} favorite={savedIds.has(food.id)} onFavorite={(item) => { if (!localStorage.getItem('dnfg_token')) { navigate('/login'); return; } favoriteMutation.mutate({ food: item, favorite: savedIds.has(item.id) }); }} />)}</div></DataState><Pagination page={page} total={query.data?.meta.total ?? 0} limit={12} onChange={(next) => update('page', String(next))} />
  </div>;
}

export function FoodDetailPage() {
  const id = Number(useParams().id);
  const query = useQuery({ queryKey: queryKeys.food(id), queryFn: () => getFood(id), enabled: Number.isInteger(id) && id > 0 });
  const client = useQueryClient();
  const navigate = useNavigate();
  const favorites = useQuery({ queryKey: queryKeys.favorites, queryFn: getFavorites, enabled: Boolean(localStorage.getItem('dnfg_token')) });
  const favoriteMutation = useMutation({
    mutationFn: (saved: boolean) => saved ? removeFavorite('FOOD', id) : addFavorite({ targetType: 'FOOD', targetId: id }),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.favorites })
  });
  if (!query.data) return <DataState loading={query.isLoading} error={query.error} empty={!query.isLoading && !query.error} retry={() => void query.refetch()}><></></DataState>;
  const { data: food } = query;
  const saved = Boolean(favorites.data?.foods.some((item) => item.id === food.id));
  return <div className="content-page"><Link to="/foods" className="back-link">← Tất cả món ngon</Link>{favoriteMutation.error && <p className="form-error" role="alert">{favoriteMutation.error.message}</p>}<section className="detail-hero"><img src={food.imageUrl} alt={food.name} /><div><span className="eyebrow">{categoryLabel(food.category)}</span><h1>{food.name}</h1><p>{food.description}</p><span className="detail-price">{formatPrice(food.priceMin)} – {formatPrice(food.priceMax)}</span><button className="button" onClick={() => { if (!localStorage.getItem('dnfg_token')) { navigate('/login'); return; } favoriteMutation.mutate(saved); }}>{saved ? '♥ Đã yêu thích' : '♡ Thêm yêu thích'}</button></div></section><div className="section"><PageHeading title={`Quán bán ${food.name}`} description="Những địa chỉ để bạn thưởng thức món ngon này." /><DataState loading={query.isLoading} error={query.error} empty={!food.restaurants.length} retry={() => void query.refetch()}><div className="restaurant-grid">{food.restaurants.map((restaurant) => <RestaurantCard key={restaurant.id} restaurant={restaurant} />)}</div></DataState></div></div>;
}

export function RestaurantListPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const district = params.get('district') ?? '';
  const foodId = params.get('foodId') ? Number(params.get('foodId')) : undefined;
  const priceLevel = params.get('priceLevel') ? Number(params.get('priceLevel')) : undefined;
  const sort = params.get('sort') ?? 'rating';
  const page = Number(params.get('page') ?? '1');
  const [search, setSearch] = useState(q);
  const filters = useMemo(() => ({ q, district, foodId, priceLevel, sort, page, limit: 12 }), [q, district, foodId, priceLevel, sort, page]);
  const query = useQuery({ queryKey: queryKeys.restaurants(filters), queryFn: () => getRestaurants(filters) });
  const update = (key: string, value: string) => setParams((current) => { const next = new URLSearchParams(current); if (value) next.set(key, value); else next.delete(key); next.delete('page'); return next; });
  const favorites = useQuery({ queryKey: queryKeys.favorites, queryFn: getFavorites, enabled: Boolean(localStorage.getItem('dnfg_token')) });
  const client = useQueryClient();
  const navigate = useNavigate();
  const toggle = useMutation({
    mutationFn: ({ restaurant, isFavorite }: { restaurant: Restaurant; isFavorite: boolean }) => isFavorite ? removeFavorite('RESTAURANT', restaurant.id) : addFavorite({ targetType: 'RESTAURANT', targetId: restaurant.id }),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.favorites })
  });
  const saved = new Set(favorites.data?.restaurants.map((item) => item.id) ?? []);
  return <div className="content-page"><PageHeading eyebrow="Ăn gì hôm nay?" title="Khám phá quán ăn" description="Những quán ngon được người địa phương yêu thích." />
    <div className="filter-bar"><SearchBox value={search} onChange={(value) => { setSearch(value); update('q', value); }} placeholder="Tên quán, món ăn..." /><div className="select-filters"><label className="filter-select">Quận<select aria-label="Lọc theo quận" value={district} onChange={(event) => update('district', event.target.value)}><option value="">Tất cả quận</option>{['Hải Châu', 'Sơn Trà', 'Ngũ Hành Sơn', 'Thanh Khê', 'Liên Chiểu', 'Cẩm Lệ'].map((value) => <option key={value}>{value}</option>)}</select></label><label className="filter-select">Giá<select aria-label="Lọc theo mức giá" value={priceLevel ?? ''} onChange={(event) => update('priceLevel', event.target.value)}><option value="">Mọi mức giá</option><option value="1">Bình dân</option><option value="2">Vừa phải</option><option value="3">Cao cấp</option></select></label><label className="filter-select">Sắp xếp<select aria-label="Sắp xếp quán" value={sort} onChange={(event) => update('sort', event.target.value)}><option value="rating">Đánh giá cao</option><option value="new">Mới nhất</option></select></label></div></div>
    {toggle.error && <p className="form-error" role="alert">{toggle.error.message}</p>}<DataState loading={query.isLoading} error={query.error} empty={!query.data?.items.length} retry={() => void query.refetch()}><div className="restaurant-grid">{query.data?.items.map((restaurant) => <RestaurantCard key={restaurant.id} restaurant={restaurant} favorite={saved.has(restaurant.id)} onFavorite={(item) => { if (!localStorage.getItem('dnfg_token')) { navigate('/login'); return; } toggle.mutate({ restaurant: item, isFavorite: saved.has(item.id) }); }} />)}</div></DataState><Pagination page={page} total={query.data?.meta.total ?? 0} limit={12} onChange={(next) => update('page', String(next))} />
  </div>;
}

export function RestaurantDetailPage() {
  const id = Number(useParams().id);
  const client = useQueryClient();
  const navigate = useNavigate();
  const detail = useQuery({ queryKey: queryKeys.restaurant(id), queryFn: () => getRestaurant(id), enabled: Number.isInteger(id) && id > 0 });
  const reviews = useQuery({ queryKey: queryKeys.reviews(id, 1), queryFn: () => getReviews(id), enabled: Number.isInteger(id) && id > 0 });
  const favorite = useMutation({
    mutationFn: (isFavorite: boolean) => isFavorite ? removeFavorite('RESTAURANT', id) : addFavorite({ targetType: 'RESTAURANT', targetId: id }),
    onMutate: async (isFavorite) => {
      await client.cancelQueries({ queryKey: queryKeys.restaurant(id) });
      const old = client.getQueryData(queryKeys.restaurant(id));
      client.setQueryData(queryKeys.restaurant(id), (current: typeof detail.data) => current ? { ...current, isFavorite: !isFavorite } : current);
      return { old };
    },
    onError: (_error, _variables, context) => client.setQueryData(queryKeys.restaurant(id), context?.old),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: queryKeys.restaurant(id) });
      void client.invalidateQueries({ queryKey: queryKeys.favorites });
    }
  });
  const review = useMutation({
    mutationFn: (input: { rating: number; comment: string }) => saveReview(id, input),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.reviews(id, 1) });
      void client.invalidateQueries({ queryKey: queryKeys.restaurant(id) });
    }
  });
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const submitReview = (event: FormEvent) => {
    event.preventDefault();
    if (!localStorage.getItem('dnfg_token')) { navigate('/login'); return; }
    review.mutate({ rating, comment: comment.trim() }, { onSuccess: () => setComment('') });
  };
  if (!detail.data) return <DataState loading={detail.isLoading} error={detail.error} empty={!detail.isLoading && !detail.error} retry={() => void detail.refetch()}><></></DataState>;
  const restaurant = detail.data;
  return <div className="content-page"><Link to="/restaurants" className="back-link">← Tất cả quán ăn</Link><section className="restaurant-detail-hero"><img src={restaurant.imageUrl} alt={restaurant.name} /><div className="detail-overlay"><span className="eyebrow">{restaurant.district} · {restaurant.openTime} – {restaurant.closeTime}</span><h1>{restaurant.name}</h1><StarRating rating={restaurant.ratingAvg} count={restaurant.ratingCount} /><p>{restaurant.address}</p><div className="hero-actions"><a className="button primary" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/directions?to=${restaurant.lat},${restaurant.lng}`}>Chỉ đường (OpenStreetMap) ↗</a><button className="button outline-light" onClick={() => favorite.mutate(Boolean(restaurant.isFavorite))}>{restaurant.isFavorite ? '♥ Đã yêu thích' : '♡ Yêu thích'}</button></div></div></section>
    {favorite.error && <p className="form-error" role="alert">{favorite.error.message}</p>}<div className="detail-columns"><div><section className="detail-section"><h2>Về quán</h2><p>{restaurant.description}</p><p><strong>Địa chỉ:</strong> {restaurant.address}</p>{restaurant.phone && <p><strong>Điện thoại:</strong> <a href={`tel:${restaurant.phone}`}>{restaurant.phone}</a></p>}<p><strong>Mức giá:</strong> {'₫'.repeat(restaurant.priceLevel)}</p></section><section className="detail-section"><h2>Món ngon tại quán</h2>{restaurant.foods.length ? <div className="selling-foods">{restaurant.foods.map((food) => <Link className="selling-food" key={food.id} to={`/foods/${food.id}`}><img src={food.imageUrl} alt="" /><span><strong>{food.name}</strong><small>{food.isSignature ? 'Món đặc trưng' : categoryLabel(food.category)}</small></span><b>{food.price ? formatPrice(food.price) : ''}</b></Link>)}</div> : <div className="inline-state">Chưa có thông tin món ăn.</div>}</section>
      <section className="detail-section"><h2>Đánh giá từ thực khách</h2><form className="review-form" onSubmit={submitReview}><label className="form-field"><span>Chấm điểm món ăn</span><div className="star-picker" role="radiogroup" aria-label="Chọn số sao">{[1, 2, 3, 4, 5].map((value) => <button type="button" key={value} aria-label={`${value} sao`} aria-pressed={rating === value} onClick={() => setRating(value)}>{value <= rating ? '★' : '☆'}</button>)}</div></label><label className="form-field"><span>Chia sẻ trải nghiệm của bạn</span><textarea value={comment} maxLength={500} onChange={(event) => setComment(event.target.value)} placeholder="Món ăn, không gian, dịch vụ..." required /></label>{review.error && <p className="form-error">{review.error.message}</p>}<button className="button primary" disabled={review.isPending}>Gửi đánh giá</button></form>
        <DataState loading={reviews.isLoading} error={reviews.error} empty={!reviews.data?.items.length} retry={() => void reviews.refetch()}><div className="reviews-list">{reviews.data?.items.map((entry) => <article className="review-item" key={entry.id}><div className="review-avatar">{entry.user.name.slice(0, 1).toLocaleUpperCase()}</div><div><div className="review-byline"><strong>{entry.user.name}</strong><StarRating rating={entry.rating} size="small" /></div><p>{entry.comment}</p><small>{new Date(entry.createdAt).toLocaleDateString('vi-VN')}</small></div></article>)}</div></DataState>
      </section></div><aside className="detail-aside"><div className="map-card"><MapPanel markers={[{ lat: restaurant.lat, lng: restaurant.lng, label: restaurant.name, address: restaurant.address }]} /><a className="map-open-link" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/?mlat=${restaurant.lat}&mlon=${restaurant.lng}#map=17/${restaurant.lat}/${restaurant.lng}`}>Mở bản đồ ↗</a></div><div className="hours-card"><h3>Giờ mở cửa</h3><p>Hằng ngày <strong>{restaurant.openTime} – {restaurant.closeTime}</strong></p><span className="open-status">● Kiểm tra trước khi ghé</span></div></aside></div>
  </div>;
}

export function ArticleListPage() {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: queryKeys.articles(page), queryFn: () => getArticles({ page, limit: 9 }) });
  return <div className="content-page"><PageHeading eyebrow="Cẩm nang địa phương" title="Chuyện ngon Đà Nẵng" description="Cùng khám phá những câu chuyện và bí kíp ăn ngon của thành phố biển." /><DataState loading={query.isLoading} error={query.error} empty={!query.data?.items.length} retry={() => void query.refetch()}><div className="article-grid">{query.data?.items.map((article) => <Link className="article-card" to={`/articles/${article.slug}`} key={article.id}><img src={article.coverUrl} alt={article.title} loading="lazy" /><div><span className="eyebrow">Cẩm nang Đà Nẵng</span><h3>{article.title}</h3><p>{article.summary}</p><span className="text-link">Đọc bài viết →</span></div></Link>)}</div></DataState><Pagination page={page} total={query.data?.meta.total ?? 0} limit={9} onChange={setPage} /></div>;
}

export function ArticleDetailPage() {
  const slug = useParams().slug ?? '';
  const query = useQuery({ queryKey: queryKeys.article(slug), queryFn: () => getArticle(slug), enabled: Boolean(slug) });
  if (!query.data) return <div className="content-page"><DataState loading={query.isLoading} error={query.error} empty={!query.isLoading && !query.error} retry={() => void query.refetch()}><></></DataState></div>;
  const article = query.data;
  return <article className="article-detail"><Link to="/articles" className="back-link">← Cẩm nang</Link><span className="eyebrow">Chuyện ngon Đà Nẵng</span><h1>{article.title}</h1><p className="article-summary">{article.summary}</p>{article.coverUrl && <img className="article-cover" src={article.coverUrl} alt={article.title} />}<div className="markdown-body"><ReactMarkdown rehypePlugins={[rehypeSanitize]}>{article.content}</ReactMarkdown></div></article>;
}

function formatPrice(value: number): string {
  return `${new Intl.NumberFormat('vi-VN').format(value)}đ`;
}
