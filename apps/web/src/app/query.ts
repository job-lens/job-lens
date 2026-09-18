import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/shared/api/client';
export function createQueryClient() {
  return new QueryClient({ defaultOptions: {
    queries: { staleTime: 15_000, refetchOnWindowFocus: true,
      retry: (count, error) => count < 2 && error instanceof ApiError && [502,503,504].includes(error.status) },
    mutations: { retry: false },
  } });
}
