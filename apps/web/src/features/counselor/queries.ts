import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, confirmHeaders, unwrap, updateHeaders } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';

type MatchWrite = components['schemas']['MatchWrite'];

/** 辅导员已授权个案列表。首页与个案列表共用，靠同一 queryKey 共享缓存。 */
export function useCases() {
  return useQuery({
    queryKey: ['cases'],
    queryFn: async ({ signal }) => unwrap(await api.GET('/cases', { signal })),
  });
}

/** 辅导员工作台摘要。进度卡只拿得到「待完成」计数，总数/已完成待后端补（Issue #2）。 */
export function useCounselorDashboard() {
  return useQuery({
    queryKey: ['dashboard', 'counselor'],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET('/dashboard', { params: { query: { view: 'counselor' } }, signal })),
  });
}

export function useCase(caseId: string) {
  return useQuery({
    queryKey: ['case', caseId],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET('/cases/{case_id}', { params: { path: { case_id: caseId } }, signal })),
  });
}

export function useCaseProfile(caseId: string) {
  return useQuery({
    queryKey: ['case-profile', caseId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/cases/{case_id}/profile', {
          params: { path: { case_id: caseId } },
          signal,
        }),
      ),
  });
}

export function useMatch(caseId: string) {
  return useQuery({
    queryKey: ['match', caseId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/cases/{case_id}/match', {
          params: { path: { case_id: caseId } },
          signal,
        }),
      ),
  });
}

export function useSaveMatch(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ version, body }: { version: number; body: MatchWrite }) =>
      unwrap(
        await api.PUT('/cases/{case_id}/match', {
          params: { path: { case_id: caseId }, header: updateHeaders(version) },
          body,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['match', caseId] }),
  });
}

export function useConfirmMatch(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ version }: { version: number }) =>
      unwrap(
        await api.POST('/cases/{case_id}/match/confirm', {
          // 重复提交由服务端 ACTIVE_TASK_EXISTS 兜底，随机幂等键安全。
          params: {
            path: { case_id: caseId },
            header: confirmHeaders(version, crypto.randomUUID()),
          },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['match', caseId] });
      // 确认后个案 display_status 变为 sop_pending，刷新列表。
      qc.invalidateQueries({ queryKey: ['cases'] });
    },
  });
}

/** 个案能力报告：描述性训练记录（无能力评分，只读观测事实）。 */
export function useRecords(caseId: string) {
  return useQuery({
    queryKey: ['case-records', caseId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/cases/{case_id}/records', {
          params: { path: { case_id: caseId } },
          signal,
        }),
      ),
  });
}
