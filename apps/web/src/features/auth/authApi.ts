import { api, setCsrfToken, unwrap } from '@/shared/api/client';
export async function prepareCsrf() {
  const result = unwrap(await api.GET('/auth/csrf'));
  setCsrfToken(result.csrf_token);
}
