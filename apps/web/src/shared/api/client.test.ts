import { describe, expect, it, vi } from 'vitest';
import { ApiError, commandHeaders, createApiClient, unwrap } from './client';

describe('contract transport', () => {
  it('preserves concurrency headers', () => {
    expect(commandHeaders(7, 'operation-1234567')).toEqual({ 'If-Match':'"7"', 'Idempotency-Key':'operation-1234567' });
    expect(() => commandHeaders(0, 'operation-1234567')).toThrow();
  });
  it('maps error responses without treating 412 as success', () => {
    expect(() => unwrap({ response:new Response('', {status:412}), error:{code:'VERSION_CONFLICT',title:'请刷新',trace_id:'trace'} })).toThrow(ApiError);
  });
  it('injects CSRF and keeps credentials out of URL', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, {status:204}));
    const { client, setCsrfToken } = createApiClient(fetcher);
    setCsrfToken('csrf-token-for-current-session');
    await client.POST('/auth/logout', { baseUrl:'https://job-lens.invalid/api/v1', params:{ header:{'X-CSRF-Token':'csrf-token-for-current-session'} } });
    const request = fetcher.mock.calls[0][0] as Request;
    expect(request.headers.get('X-CSRF-Token')).toBe('csrf-token-for-current-session');
    expect(request.credentials).toBe('same-origin');
    expect(request.url).not.toContain('csrf-token');
  });
});

it('preserves native request cancellation in Node 24 and jsdom', async () => {
  const controller = new AbortController();
  const fetcher = vi.fn<typeof fetch>(async input => {
    const request = input as Request;
    return new Promise<Response>((_resolve, reject) => {
      request.signal.addEventListener('abort', () => reject(request.signal.reason), { once: true });
    });
  });
  const { client } = createApiClient(fetcher);
  const pending = client.GET('/me', { signal: controller.signal });
  const rejection = expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  await vi.waitFor(() => expect(fetcher).toHaveBeenCalledOnce());
  controller.abort();
  await rejection;
});
