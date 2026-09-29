import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, confirmHeaders, createHeaders, unwrap, updateHeaders } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';

type FeedbackCreate = components['schemas']['FeedbackCreate'];
type PromptOverrideWrite = components['schemas']['PromptOverrideWrite'];
type AnnotationCreate = components['schemas']['AnnotationCreate'];

/** 读取提交快照。父任务 version 经 ETag/task_version 投影，审核时用作 If-Match。 */
export function useSubmission(submissionId: string) {
  return useQuery({
    queryKey: ['submission', submissionId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/submissions/{submission_id}', {
          params: { path: { submission_id: submissionId } },
          signal,
        }),
      ),
  });
}

/** 提交快照只带 step_id 与状态，不含步骤说明；拉取对应 SOP 版本以展示步骤内容。 */
export function useSnapshotRevision(revisionId: string) {
  return useQuery({
    queryKey: ['training-revision', revisionId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/sop-revisions/{revision_id}', {
          params: { path: { revision_id: revisionId } },
          signal,
        }),
      ),
  });
}

/** 审核提交：If-Match 用父任务 task_version；幂等键保证「一份主反馈」。 */
export function useFeedback(submissionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ version, body }: { version: number; body: FeedbackCreate }) =>
      unwrap(
        await api.POST('/submissions/{submission_id}/feedback', {
          params: {
            path: { submission_id: submissionId },
            header: confirmHeaders(version, crypto.randomUUID()),
          },
          body,
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['submission', submissionId] });
      // 审核会推进/回退任务状态，刷新个案列表与工作台「待反馈」计数。
      qc.invalidateQueries({ queryKey: ['cases'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/** 读取单个训练任务（固定内容 + 进度 + 提示等级覆盖）。 */
export function useTask(taskId: string) {
  return useQuery({
    queryKey: ['task', taskId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/tasks/{task_id}', {
          params: { path: { task_id: taskId } },
          signal,
        }),
      ),
  });
}

/** 调整任务文字提示等级：PUT + If-Match（put_headers）。 */
export function usePromptOverride(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ version, body }: { version: number; body: PromptOverrideWrite }) =>
      unwrap(
        await api.PUT('/tasks/{task_id}/prompt-override', {
          params: { path: { task_id: taskId }, header: updateHeaders(version) },
          body,
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['task', taskId] });
    },
  });
}

/** 辅导员取消任务：POST 命令 + If-Match + 幂等键（command_headers）。 */
export function useCancelTask(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ version, reason }: { version: number; reason: string }) =>
      unwrap(
        await api.POST('/tasks/{task_id}/actions', {
          params: {
            path: { task_id: taskId },
            header: confirmHeaders(version, crypto.randomUUID()),
          },
          body: { action: 'cancel', reason },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['task', taskId] });
      qc.invalidateQueries({ queryKey: ['cases'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/** 创建指引标注草稿：POST + CSRF + 幂等键（write_headers，无 If-Match）。 */
export function useCreateAnnotation(taskId: string) {
  return useMutation({
    mutationFn: async (body: AnnotationCreate) =>
      unwrap(
        await api.POST('/tasks/{task_id}/annotations', {
          params: { path: { task_id: taskId }, header: createHeaders(crypto.randomUUID()) },
          body,
        }),
      ),
  });
}
