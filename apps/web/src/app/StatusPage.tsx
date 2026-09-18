import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';

export function StatusPage() {
  const status = useQuery({ queryKey: ['health'], queryFn: async ({ signal }) => unwrap(await api.GET('/health/ready', { signal })) });
  return <section><h1>融职境工程入口</h1><p>Web、API 与数据库连接检查。</p>
    {status.isPending && <LoadingState />}
    {status.isError && <ErrorPanel message="后端或数据库尚未就绪" retry={() => void status.refetch()} />}
    {status.isSuccess && <p role="status">API 与数据库已连接</p>}
  </section>;
}
