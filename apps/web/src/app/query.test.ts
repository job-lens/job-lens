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
