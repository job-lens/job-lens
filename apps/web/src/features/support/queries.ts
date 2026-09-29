import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, confirmHeaders, createHeaders, unwrap } from '@/shared/api/client';

/** 辅导员可见求助列表，可按状态过滤。 */
export function useAssistanceRequests(state?: 'queued' | 'accepted' | 'resolved' | 'cancelled') {
  return useQuery({
    queryKey: ['assistance-requests', state ?? 'all'],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/assistance-requests', {
          params: { query: state ? { state } : {} },
          signal,
        }),
      ),
  });
}

export function useAssistance(requestId: string) {
  return useQuery({
    queryKey: ['assistance', requestId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/assistance-requests/{request_id}', {
          params: { path: { request_id: requestId } },
          signal,
        }),
      ),
  });
}

export function useAssistanceMessages(requestId: string) {
  return useQuery({
    queryKey: ['assistance-messages', requestId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/assistance-requests/{request_id}/messages', {
          params: { path: { request_id: requestId } },
          signal,
        }),
      ),
  });
}

/** 辅导员接单 / 解决。动作是改已有聚合 + 幂等，故用 confirmHeaders（CSRF + If-Match + 幂等键）。 */
export function useAssistanceAction(requestId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ action, version }: { action: 'accept' | 'resolve'; version: number }) =>
      unwrap(
        await api.POST('/assistance-requests/{request_id}/actions', {
          params: {
            path: { request_id: requestId },
            header: confirmHeaders(version, crypto.randomUUID()),
          },
          body: { action },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assistance', requestId] });
      qc.invalidateQueries({ queryKey: ['assistance-requests'] });
    },
  });
}

export function useSendMessage(requestId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: string) =>
      unwrap(
        await api.POST('/assistance-requests/{request_id}/messages', {
          params: { path: { request_id: requestId }, header: createHeaders(crypto.randomUUID()) },
          body: { body, attachment_ids: [] },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assistance-messages', requestId] }),
  });
}
