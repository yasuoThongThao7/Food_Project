import { useQuery } from '@tanstack/react-query';
import { getMe } from '../api/endpoints';
import { getToken } from '../api/http';
import { queryKeys } from '../api/queryKeys';

export function categoryLabel(category: string): string {
  const labels: Record<string, string> = {
    noodle: 'Món nước', seafood: 'Hải sản', snack: 'Ăn vặt',
    dessert: 'Tráng miệng', drink: 'Đồ uống', other: 'Đặc sản'
  };
  return labels[category] ?? category;
}

export function useCurrentUser() {
  return useQuery({ queryKey: queryKeys.me, queryFn: getMe, enabled: Boolean(getToken()), retry: false });
}
