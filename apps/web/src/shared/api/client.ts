import createClient from 'openapi-fetch';
import type { components, paths } from './schema';

type Problem = components['schemas']['Problem'];

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly traceId?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function createApiClient(fetcher?: typeof fetch) {
  let csrfToken: string | undefined;
  const client = createClient<paths>({
    baseUrl: new URL('/api/v1', globalThis.location?.origin ?? 'http://localhost').href,
    credentials: 'same-origin',
    fetch: fetcher ?? ((...args) => globalThis.fetch(...args)),
  });
  client.use({
    onRequest({ request }) {
      if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method) && csrfToken) {
        request.headers.set('X-CSRF-Token', csrfToken);
      }
      return request;
    },
  });
  return {
    client,
    setCsrfToken: (value?: string) => {
      csrfToken = value;
    },
  };
}

export const { client: api, setCsrfToken } = createApiClient();

export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.response.ok && result.data !== undefined) return result.data;
  const error = result.error as Partial<Problem> | undefined;
  throw new ApiError(
    result.response.status,
    typeof error?.code === 'string' ? error.code : 'REQUEST_FAILED',
    typeof error?.title === 'string' ? error.title : '请求未完成，请重试',
    typeof error?.trace_id === 'string' ? error.trace_id : undefined,
  );
}

export function commandHeaders(
  version: number,
  key: string,
): { 'If-Match': string; 'Idempotency-Key': string } {
  if (!Number.isSafeInteger(version) || version < 1 || version > 2147483647)
    throw new Error('Invalid version');
  if (!/^[!-~]{16,128}$/.test(key)) throw new Error('Invalid idempotency key');
  return { 'If-Match': `"${version}"`, 'Idempotency-Key': key };
}

export function unwrapVoid(result: { response: Response; error?: unknown }): void {
  if (result.response.ok) return;
  unwrap<never>(result);
}
