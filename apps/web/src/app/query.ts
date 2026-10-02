import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
import { ApiError, setCsrfToken } from '@/shared/api/client';
export function createQueryClient() {
  function expire(error: unknown) {
    if (!(error instanceof ApiError) || error.status !== 401) return;
    setCsrfToken();
    const privateQueries = {
      predicate: (query: { queryKey: readonly unknown[] }) => query.queryKey[0] !== 'session',
    };
    void client.cancelQueries(privateQueries);
    client.removeQueries(privateQueries);
    client
      .getQueryCache()
      .find({ queryKey: ['session'], exact: true })
      ?.setState({
        data: undefined,
        error,
        status: 'error',
        fetchStatus: 'idle',
      });
  }
  const client = new QueryClient({
    queryCache: new QueryCache({ onError: expire }),
    mutationCache: new MutationCache({ onError: expire }),
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: true,
        retry: (count, error) =>
          count < 2 && error instanceof ApiError && [502, 503, 504].includes(error.status),
      },
      mutations: { retry: false },
    },
  });
  return client;
}
