import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, confirmHeaders, createHeaders, unwrap, updateHeaders } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';

type PlanCreate = components['schemas']['PlanCreate'];
type RevisionCreate = components['schemas']['RevisionCreate'];
type RevisionWrite = components['schemas']['RevisionWrite'];

/** 个案下的 SOP 计划列表（SOP 工作台入口）。一个案可有多份计划，首版默认取第一份。 */
export function usePlans(caseId: string) {
  return useQuery({
    queryKey: ['sop-plans', caseId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/cases/{case_id}/sop-plans', {
          params: { path: { case_id: caseId } },
          signal,
        }),
      ),
  });
}

/** 单个 SOP 版本（草稿或已发布）。 */
export function useRevision(revisionId: string) {
  return useQuery({
    queryKey: ['sop-revision', revisionId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/sop-revisions/{revision_id}', {
          params: { path: { revision_id: revisionId } },
          signal,
        }),
      ),
  });
}

/** 创建计划 + 初始草稿。 */
export function useCreatePlan(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PlanCreate) =>
      unwrap(
        await api.POST('/cases/{case_id}/sop-plans', {
          params: { path: { case_id: caseId }, header: createHeaders(crypto.randomUUID()) },
          body,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sop-plans', caseId] }),
  });
}

/** 基于已发布版本新建草稿（服务端保证每计划至多一份当前草稿）。 */
export function useCreateRevision(planId: string, caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: RevisionCreate) =>
      unwrap(
        await api.POST('/sop-plans/{plan_id}/revisions', {
          params: { path: { plan_id: planId }, header: createHeaders(crypto.randomUUID()) },
          body,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sop-plans', caseId] }),
  });
}

/** 整体保存草稿（PUT，乐观覆盖整份 RevisionWrite）。 */
export function useSaveRevision(revisionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ version, body }: { version: number; body: RevisionWrite }) =>
      unwrap(
        await api.PUT('/sop-revisions/{revision_id}', {
          params: { path: { revision_id: revisionId }, header: updateHeaders(version) },
          body,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sop-revision', revisionId] }),
  });
}

/** 冻结并发布 SOP，原子创建唯一训练任务。 */
export function usePublishRevision(revisionId: string, caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ version, dueOn }: { version: number; dueOn: string | null }) =>
      unwrap(
        await api.POST('/sop-revisions/{revision_id}/publish', {
          params: {
            path: { revision_id: revisionId },
            header: confirmHeaders(version, crypto.randomUUID()),
          },
          body: { due_on: dueOn },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sop-revision', revisionId] });
      // 发布后 plan.draft_revision_id 清空、published_revision_id 更新。
      qc.invalidateQueries({ queryKey: ['sop-plans', caseId] });
    },
  });
}
