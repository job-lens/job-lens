import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { api, unwrap } from '@/shared/api/client';

export function useLearnerDashboard() {
  return useQuery({
    queryKey: ['dashboard', 'learner'],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/dashboard', {
          params: { query: { view: 'learner' } },
          signal,
        }),
      ),
  });
}
export function useLearnerCases() {
  return useInfiniteQuery({
    queryKey: ['learner-cases'],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ signal, pageParam }) =>
      unwrap(
        await api.GET('/cases', {
          params: { query: { limit: 20, cursor: pageParam } },
          signal,
        }),
      ),
    getNextPageParam: page => page.next_cursor ?? undefined,
  });
}
export function useLearnerTasks() {
  return useInfiniteQuery({
    queryKey: ['tasks', 'learner'],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ signal, pageParam }) =>
      unwrap(
        await api.GET('/tasks', {
          params: { query: { limit: 20, cursor: pageParam } },
          signal,
        }),
      ),
    getNextPageParam: page => page.next_cursor ?? undefined,
  });
}
export function useLearnerRecords(caseId: string) {
  return useInfiniteQuery({
    queryKey: ['learner-records', caseId],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ signal, pageParam }) =>
      unwrap(
        await api.GET('/cases/{case_id}/records', {
          params: { path: { case_id: caseId }, query: { limit: 20, cursor: pageParam } },
          signal,
        }),
      ),
    getNextPageParam: page => page.next_cursor ?? undefined,
  });
}
