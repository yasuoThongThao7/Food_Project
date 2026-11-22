import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import {
  createArticle, createFood, createRestaurant, deleteArticle, deleteFood, deleteRestaurant,
  getAdminStats, getAdminUsers, getArticles, getFoods, getRestaurants, updateArticle,
  updateFood, updateRestaurant, updateUserBan
} from '../api/endpoints';
import { queryKeys } from '../api/queryKeys';
import type { AdminUser, Article, ArticleInput, Food, FoodCategory, FoodInput, Restaurant, RestaurantInput } from '../api/types';
import {
  ConfirmModal, DataState, FormField, PageHeading, SearchBox
} from '../components/Shared';
import { useCurrentUser } from '../components/helpers';

type AdminTab = 'overview' | 'users' | 'restaurants' | 'foods' | 'articles';
type Entity = 'restaurant' | 'food' | 'article';
type AdminRecord = Restaurant | Food | Article;

const tabLabels: Array<[AdminTab, string]> = [
  ['overview', 'Tổng quan'], ['users', 'Người dùng'], ['restaurants', 'Nhà hàng'],
  ['foods', 'Món ăn'], ['articles', 'Bài viết']
];

export default function AdminPage() {
  const [tab, setTab] = useState<AdminTab>('overview');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<{ type: Entity; item?: AdminRecord } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ type: Entity; item: AdminRecord } | null>(null);
  const [banTarget, setBanTarget] = useState<AdminUser | null>(null);
  const [banReason, setBanReason] = useState('');
  const queryClient = useQueryClient();
  const currentUser = useCurrentUser();
  const stats = useQuery({ queryKey: queryKeys.adminStats, queryFn: getAdminStats, enabled: tab === 'overview' });
  const users = useQuery({ queryKey: queryKeys.adminUsers(search, page), queryFn: () => getAdminUsers({ q: search, page }), enabled: tab === 'users' });
  const restaurants = useQuery({ queryKey: queryKeys.restaurants({ admin: true, page }), queryFn: () => getRestaurants({ page, limit: 12 }), enabled: tab === 'restaurants' });
  const foods = useQuery({ queryKey: queryKeys.foods({ admin: true, page }), queryFn: () => getFoods({ page, limit: 12 }), enabled: tab === 'foods' });
  const articles = useQuery({ queryKey: queryKeys.articles(page), queryFn: () => getArticles({ page, limit: 12 }), enabled: tab === 'articles' });

  const refresh = (type: Entity) => {
    if (type === 'restaurant') void queryClient.invalidateQueries({ queryKey: ['restaurants'] });
    if (type === 'food') void queryClient.invalidateQueries({ queryKey: ['foods'] });
    if (type === 'article') void queryClient.invalidateQueries({ queryKey: ['articles'] });
  };
  const mutations = {
    restaurant: useMutation({
      mutationFn: ({ item, id }: { item: RestaurantInput; id?: number }) => id ? updateRestaurant(id, item) : createRestaurant(item),
      onSuccess: () => { refresh('restaurant'); setEditor(null); }
    }),
    food: useMutation({
      mutationFn: ({ item, id }: { item: FoodInput; id?: number }) => id ? updateFood(id, item) : createFood(item),
      onSuccess: () => { refresh('food'); setEditor(null); }
    }),
    article: useMutation({
      mutationFn: ({ item, id }: { item: ArticleInput; id?: number }) => id ? updateArticle(id, item) : createArticle(item),
      onSuccess: () => { refresh('article'); setEditor(null); }
    }),
    ban: useMutation({
      mutationFn: ({ user, banned, reason }: { user: AdminUser; banned: boolean; reason?: string }) => updateUserBan(user.id, { banned, reason }),
      onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['admin-users'] }); setBanTarget(null); setBanReason(''); }
    }),
    deletion: useMutation({
      mutationFn: ({ type, id }: { type: Entity; id: number }) => type === 'restaurant' ? deleteRestaurant(id) : type === 'food' ? deleteFood(id) : deleteArticle(id),
      onSuccess: (_data, variables) => { refresh(variables.type); setDeleteTarget(null); }
    })
  };
  const activeError = tab === 'overview' ? stats.error : tab === 'users' ? users.error : tab === 'restaurants' ? restaurants.error : tab === 'foods' ? foods.error : articles.error;
  return <div className="content-page admin-page"><PageHeading eyebrow="Không gian quản trị" title="Quản lý nội dung" description="Quản lý dữ liệu và hoạt động của Da Nang Food Guide." />
    <div className="admin-tabs" role="tablist">{tabLabels.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? 'admin-tab active' : 'admin-tab'} onClick={() => { setTab(id); setPage(1); }}>{label}</button>)}</div>
    <DataState loading={tab === 'overview' ? stats.isLoading : tab === 'users' ? users.isLoading : tab === 'restaurants' ? restaurants.isLoading : tab === 'foods' ? foods.isLoading : articles.isLoading} error={activeError} empty={false} retry={() => {
      if (tab === 'overview') void stats.refetch();
      if (tab === 'users') void users.refetch();
      if (tab === 'restaurants') void restaurants.refetch();
      if (tab === 'foods') void foods.refetch();
      if (tab === 'articles') void articles.refetch();
    }}>
      {tab === 'overview' && <section className="stats-grid">{[
        ['Người dùng', stats.data?.users, '👥'], ['Nhà hàng', stats.data?.restaurants, '🍜'],
        ['Món ăn', stats.data?.foods, '🥢'], ['Đánh giá', stats.data?.reviews, '⭐'],
        ['Tìm kiếm 7 ngày', stats.data?.searches7d, '🔎']
      ].map(([label, count, icon]) => <div className="stat-card" key={String(label)}><span>{icon}</span><div><small>{label}</small><strong>{count ?? '—'}</strong></div></div>)}</section>}
      {tab === 'users' && <section className="admin-section"><div className="admin-section-header"><h2>Người dùng</h2><SearchBox value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Tìm tên hoặc email..." /></div><div className="table-scroll"><table><thead><tr><th>Người dùng</th><th>Vai trò</th><th>Trạng thái</th><th>Ngày tham gia</th><th>Thao tác</th></tr></thead><tbody>{users.data?.items.map((user) => {
        const self = currentUser.data?.id === user.id;
        const disabled = !currentUser.data || self || user.role === 'ADMIN';
        return <tr key={user.id}><td><strong>{user.name}</strong><small>{user.email}</small></td><td>{user.role}</td><td><span className={user.isBanned ? 'status-pill banned' : 'status-pill'}>{user.isBanned ? 'Đã khóa' : 'Hoạt động'}</span>{user.isBanned && user.banReason && <small>{user.banReason}</small>}</td><td>{new Date(user.createdAt).toLocaleDateString('vi-VN')}</td><td><button className="table-action" disabled={disabled || mutations.ban.isPending} title={disabled ? 'Không thể khóa tài khoản này' : ''} onClick={() => { setBanReason(''); setBanTarget(user); }}>{user.isBanned ? 'Mở khóa' : 'Khóa tài khoản'}</button></td></tr>;
      })}</tbody></table></div><AdminPagination page={page} total={users.data?.meta.total ?? 0} onChange={setPage} /></section>}
      {tab === 'restaurants' && <AdminRecords title="Nhà hàng" items={restaurants.data?.items ?? []} type="restaurant" onEdit={(item) => setEditor({ type: 'restaurant', item })} onDelete={(item) => setDeleteTarget({ type: 'restaurant', item })} onCreate={() => setEditor({ type: 'restaurant' })} page={page} total={restaurants.data?.meta.total ?? 0} setPage={setPage} />}
      {tab === 'foods' && <AdminRecords title="Món ăn" items={foods.data?.items ?? []} type="food" onEdit={(item) => setEditor({ type: 'food', item })} onDelete={(item) => setDeleteTarget({ type: 'food', item })} onCreate={() => setEditor({ type: 'food' })} page={page} total={foods.data?.meta.total ?? 0} setPage={setPage} />}
      {tab === 'articles' && <AdminRecords title="Bài viết" items={articles.data?.items ?? []} type="article" onEdit={(item) => setEditor({ type: 'article', item })} onDelete={(item) => setDeleteTarget({ type: 'article', item })} onCreate={() => setEditor({ type: 'article' })} page={page} total={articles.data?.meta.total ?? 0} setPage={setPage} />}
    </DataState>
    {editor && <EditorModal editor={editor} busy={mutations[editor.type].isPending} error={mutations[editor.type].error?.message ?? ''} onClose={() => setEditor(null)} onSubmit={(item) => {
      if (editor.type === 'restaurant') mutations.restaurant.mutate({ item: item as RestaurantInput, id: editor.item?.id });
      if (editor.type === 'food') mutations.food.mutate({ item: item as FoodInput, id: editor.item?.id });
      if (editor.type === 'article') mutations.article.mutate({ item: item as ArticleInput, id: editor.item?.id });
    }} />}
    {deleteTarget && <ConfirmModal title={`Xóa ${entityLabel(deleteTarget.type)}?`} danger onCancel={() => setDeleteTarget(null)} confirmText="Xóa" onConfirm={() => mutations.deletion.mutate({ type: deleteTarget.type, id: deleteTarget.item.id })}><p>Nội dung sẽ được ẩn khỏi hệ thống. Bạn có chắc chắn muốn tiếp tục?</p>{mutations.deletion.error && <p className="form-error">{mutations.deletion.error.message}</p>}</ConfirmModal>}
    {banTarget && <ConfirmModal title={banTarget.isBanned ? 'Mở khóa tài khoản' : 'Khóa tài khoản'} onCancel={() => setBanTarget(null)} confirmText={banTarget.isBanned ? 'Mở khóa' : 'Khóa tài khoản'} danger={!banTarget.isBanned} onConfirm={() => mutations.ban.mutate({ user: banTarget, banned: !banTarget.isBanned, reason: banReason || undefined })}><p>{banTarget.isBanned ? `Mở khóa cho ${banTarget.name}?` : `Khóa tài khoản ${banTarget.name}?`}</p>{!banTarget.isBanned && <FormField label="Lý do khóa"><textarea value={banReason} onChange={(event) => setBanReason(event.target.value)} placeholder="Nhập lý do để thông báo cho người dùng..." required /></FormField>}{mutations.ban.error && <p className="form-error">{mutations.ban.error.message}</p>}</ConfirmModal>}
  </div>;
}

function AdminRecords({ title, items, type, onEdit, onDelete, onCreate, page, total, setPage }: { title: string; items: AdminRecord[]; type: Entity; onEdit: (item: AdminRecord) => void; onDelete: (item: AdminRecord) => void; onCreate: () => void; page: number; total: number; setPage: (page: number) => void }) {
  return <section className="admin-section"><div className="admin-section-header"><h2>{title}</h2><button className="button primary small" onClick={onCreate}>＋ Thêm {entityLabel(type)}</button></div><div className="table-scroll"><table><thead><tr><th>Tên</th><th>{type === 'restaurant' ? 'Địa chỉ' : type === 'food' ? 'Nhãn AI' : 'Slug'}</th><th>Thông tin</th><th>Thao tác</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td><strong>{recordTitle(item, type)}</strong></td><td>{type === 'restaurant' ? (item as Restaurant).address : type === 'food' ? (item as Food).aiLabel : (item as Article).slug}</td><td>{type === 'restaurant' ? (item as Restaurant).district : type === 'food' ? (item as Food).category : (item as Article).isPublished ? 'Đã xuất bản' : 'Bản nháp'}</td><td className="row-actions"><button className="table-action" onClick={() => onEdit(item)}>Sửa</button><button className="table-action danger-text" onClick={() => onDelete(item)}>Xóa</button></td></tr>)}</tbody></table>{items.length === 0 && <p className="table-empty">Chưa có nội dung.</p>}</div><AdminPagination page={page} total={total} onChange={setPage} /></section>;
}

function EditorModal({ editor, busy, error, onClose, onSubmit }: { editor: { type: Entity; item?: AdminRecord }; busy: boolean; error: string; onClose: () => void; onSubmit: (item: RestaurantInput | FoodInput | ArticleInput) => void }) {
  const [preview, setPreview] = useState(false);
  const original = editor.item;
  const [articleContent, setArticleContent] = useState((original as Article | undefined)?.content ?? '');
  const handle = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const value = (name: string) => String(form.get(name) ?? '').trim();
    const number = (name: string) => Number(form.get(name));
    if (editor.type === 'restaurant') {
      const input: RestaurantInput = {
        name: value('name'), slug: value('slug'), address: value('address'), district: value('district'),
        lat: value('lat') ? number('lat') : null, lng: value('lng') ? number('lng') : null,
        phone: value('phone') || null, openTime: value('openTime'), closeTime: value('closeTime'),
        priceLevel: number('priceLevel') as 1 | 2 | 3, imageUrl: value('imageUrl'), description: value('description'),
        mealSlots: value('mealSlots')
          .split(',')
          .map((slot) => slot.trim())
          .filter((slot): slot is RestaurantInput['mealSlots'][number] =>
            ['breakfast', 'lunch', 'snack', 'dinner'].includes(slot)
          )
      };
      onSubmit(input);
    } else if (editor.type === 'food') {
      const input: FoodInput = {
        name: value('name'), slug: value('slug'), aiLabel: value('aiLabel'), description: value('description'),
        category: value('category') as FoodCategory, imageUrl: value('imageUrl'),
        priceMin: number('priceMin'), priceMax: number('priceMax')
      };
      onSubmit(input);
    } else {
      const input: ArticleInput = {
        title: value('title'), slug: value('slug'), summary: value('summary'), content: articleContent,
        coverUrl: value('coverUrl'), isPublished: form.get('isPublished') === 'on'
      };
      onSubmit(input);
    }
  };
  const title = `${original ? 'Chỉnh sửa' : 'Thêm'} ${entityLabel(editor.type)}`;
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="modal modal-wide" role="dialog" aria-modal="true" aria-labelledby="editor-heading"><button className="modal-close" aria-label="Đóng" onClick={onClose}>×</button><h2 id="editor-heading">{title}</h2><form className="form-stack editor-form" onSubmit={handle}>
    {editor.type === 'restaurant' && <><FormField label="Tên nhà hàng"><input name="name" defaultValue={(original as Restaurant | undefined)?.name} required /></FormField><FormField label="Slug"><input name="slug" defaultValue={(original as Restaurant | undefined)?.slug} required /></FormField><FormField label="Địa chỉ"><input name="address" defaultValue={(original as Restaurant | undefined)?.address} required /></FormField><FormField label="Quận"><input name="district" defaultValue={(original as Restaurant | undefined)?.district} required /></FormField><div className="form-row"><FormField label="Vĩ độ (không bắt buộc)"><input name="lat" type="number" step="any" defaultValue={(original as Restaurant | undefined)?.lat} /></FormField><FormField label="Kinh độ (không bắt buộc)"><input name="lng" type="number" step="any" defaultValue={(original as Restaurant | undefined)?.lng} /></FormField></div><p className="helper-text">Để trống tọa độ để máy chủ tự định vị theo địa chỉ Đà Nẵng.</p><div className="form-row"><FormField label="Giờ mở cửa"><input name="openTime" type="time" defaultValue={(original as Restaurant | undefined)?.openTime ?? '07:00'} required /></FormField><FormField label="Giờ đóng cửa"><input name="closeTime" type="time" defaultValue={(original as Restaurant | undefined)?.closeTime ?? '21:00'} required /></FormField></div><div className="form-row"><FormField label="Mức giá"><select name="priceLevel" defaultValue={(original as Restaurant | undefined)?.priceLevel ?? 1}><option value="1">Bình dân</option><option value="2">Vừa phải</option><option value="3">Cao cấp</option></select></FormField><FormField label="Điện thoại"><input name="phone" defaultValue={(original as Restaurant | undefined)?.phone ?? ''} /></FormField></div><FormField label="Link ảnh"><input name="imageUrl" type="url" defaultValue={(original as Restaurant | undefined)?.imageUrl} /></FormField><FormField label="Mô tả"><textarea name="description" defaultValue={(original as Restaurant | undefined)?.description} rows={3} /></FormField><FormField label="Khung giờ phục vụ"><input name="mealSlots" defaultValue={(original as Restaurant | undefined)?.mealSlots ?? 'breakfast,lunch,snack,dinner'} /><small>Giá trị phân cách bằng dấu phẩy: breakfast, lunch, snack, dinner</small></FormField></>}
    {editor.type === 'food' && <><FormField label="Tên món ăn"><input name="name" defaultValue={(original as Food | undefined)?.name} required /></FormField><FormField label="Slug"><input name="slug" defaultValue={(original as Food | undefined)?.slug} required /></FormField><FormField label="Nhãn AI (aiLabel)"><input name="aiLabel" defaultValue={(original as Food | undefined)?.aiLabel} required /><small className="helper-text">Đây là nhãn do AI trả về khi nhận diện món ăn.</small></FormField><FormField label="Danh mục"><select name="category" defaultValue={(original as Food | undefined)?.category ?? 'other'}>{[['noodle', 'Món nước'], ['seafood', 'Hải sản'], ['snack', 'Ăn vặt'], ['dessert', 'Tráng miệng'], ['drink', 'Đồ uống'], ['other', 'Khác']].map(([value, name]) => <option value={value} key={value}>{name}</option>)}</select></FormField><div className="form-row"><FormField label="Giá thấp nhất"><input name="priceMin" type="number" min={0} defaultValue={(original as Food | undefined)?.priceMin ?? 0} required /></FormField><FormField label="Giá cao nhất"><input name="priceMax" type="number" min={0} defaultValue={(original as Food | undefined)?.priceMax ?? 0} required /></FormField></div><FormField label="Link ảnh"><input name="imageUrl" type="url" defaultValue={(original as Food | undefined)?.imageUrl} /></FormField><FormField label="Mô tả"><textarea name="description" defaultValue={(original as Food | undefined)?.description} rows={4} /></FormField></>}
    {editor.type === 'article' && <><FormField label="Tiêu đề"><input name="title" defaultValue={(original as Article | undefined)?.title} required /></FormField><FormField label="Slug"><input name="slug" defaultValue={(original as Article | undefined)?.slug} required /></FormField><FormField label="Tóm tắt"><textarea name="summary" defaultValue={(original as Article | undefined)?.summary} rows={2} required /></FormField><FormField label="Ảnh bìa URL"><input name="coverUrl" type="url" defaultValue={(original as Article | undefined)?.coverUrl} /></FormField><div className="preview-toolbar"><span>Nội dung Markdown</span><button type="button" className="text-button" onClick={() => setPreview(!preview)}>{preview ? 'Chỉnh sửa' : 'Xem trước'}</button></div>{preview ? <div className="markdown-preview"><ReactMarkdown rehypePlugins={[rehypeSanitize]}>{articleContent}</ReactMarkdown></div> : <FormField label="Nội dung"><textarea name="content" value={articleContent} onChange={(event) => setArticleContent(event.target.value)} rows={10} required /></FormField>}<label className="checkbox-field"><input name="isPublished" type="checkbox" defaultChecked={(original as Article | undefined)?.isPublished ?? false} /> Xuất bản bài viết</label></>}
    {error && <p className="form-error" role="alert">{error}</p>}<div className="modal-actions"><button type="button" className="button" onClick={onClose}>Hủy</button><button className="button primary" disabled={busy}>{busy ? 'Đang lưu...' : 'Lưu thay đổi'}</button></div>
  </form></section></div>;
}

function AdminPagination({ page, total, onChange }: { page: number; total: number; onChange: (page: number) => void }) {
  const pages = Math.ceil(total / 12);
  return pages > 1 ? <div className="pagination"><button disabled={page <= 1} onClick={() => onChange(page - 1)}>← Trước</button><span>Trang {page} / {pages}</span><button disabled={page >= pages} onClick={() => onChange(page + 1)}>Sau →</button></div> : null;
}

function entityLabel(type: Entity): string {
  return type === 'restaurant' ? 'nhà hàng' : type === 'food' ? 'món ăn' : 'bài viết';
}

function recordTitle(item: AdminRecord, type: Entity): string {
  if (type === 'restaurant') return (item as Restaurant).name;
  if (type === 'food') return (item as Food).name;
  return (item as Article).title;
}
