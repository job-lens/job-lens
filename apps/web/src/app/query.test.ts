import { expect, it } from 'vitest';
import { ApiError } from '@/shared/api/client';
import { createQueryClient } from './query';

it('expires the gate and removes private cached data when any protected request returns 401', async () => {
  const client = createQueryClient();
  client.setQueryData(['session'], { id: 'learner', roles: ['learner'] });
  client.setQueryData(['tasks'], [{ title: 'private task' }]);
  await expect(
    client.fetchQuery({
      queryKey: ['profile'],
      queryFn: () => {
        throw new ApiError(401, 'SESSION_EXPIRED', '会话失效');
      },
    }),
  ).rejects.toThrow(ApiError);
  expect(client.getQueryData(['tasks'])).toBeUndefined();
  expect(client.getQueryState(['session'])?.status).toBe('error');
  expect(client.getQueryData(['session'])).toBeUndefined();
});

it('leaves public health checks alone when an anonymous request returns 401', async () => {
  const client = createQueryClient();
  client.setQueryData(['health'], { status: 'ok' });
  await expect(
    client.fetchQuery({
      queryKey: ['preferences'],
      queryFn: () => {
        throw new ApiError(401, 'UNAUTHENTICATED', '请登录');
      },
    }),
  ).rejects.toThrow(ApiError);
  expect(client.getQueryData(['health'])).toEqual({ status: 'ok' });
});
