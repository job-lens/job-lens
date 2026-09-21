import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, createHeaders, unwrap, unwrapVoid } from '@/shared/api/client';

/** 补拉本人持久化通知（after_seq 默认 0，从最早保留的记录开始）。 */
export function useNotifications() {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/notifications', {
          params: { query: { limit: 50 } },
          signal,
        }),
      ),
  });
}

/** 标记通知已读：POST + CSRF + 幂等键（write_headers）。 */
export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (notificationId: string) =>
      unwrapVoid(
        await api.POST('/notifications/{notification_id}/read', {
          params: {
            path: { notification_id: notificationId },
            header: createHeaders(crypto.randomUUID()),
          },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}
