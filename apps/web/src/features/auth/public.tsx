import { useQuery } from '@tanstack/react-query';
import { Navigate, Outlet } from 'react-router';
import { api, ApiError, unwrap } from '@/shared/api/client';
import { ErrorPanel, LoadingState, ModulePage } from '@/shared/ui/AsyncState';

export function SessionGate({ role }: { role?: 'learner' | 'counselor' }) {
  const user = useQuery({
    queryKey: ['session'],
    queryFn: async ({ signal }) => unwrap(await api.GET('/me', { signal })),
  });
  if (user.isPending) return <LoadingState />;
  if (user.error instanceof ApiError && user.error.status === 401)
    return <Navigate to="/login" replace />;
  if (user.isError)
    return <ErrorPanel message="身份服务暂不可用" retry={() => void user.refetch()} />;
  if (role && !user.data.roles.includes(role)) return <ErrorPanel message="无权访问此区域" />;
  return <Outlet />;
}
export function LoginPage() {
  return (
    <ModulePage title="登录">
      <p>账号登录流程将在身份模块接入。</p>
    </ModulePage>
  );
}
