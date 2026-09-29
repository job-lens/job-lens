import type { components } from '@/shared/api/schema';

export type DisplayStatus = components['schemas']['Case']['display_status'];

/** 派生状态 → 中文文案。个案列表、画像、首页三处共用，保证口径一致。 */
export const DISPLAY_STATUS_LABELS: Record<DisplayStatus, string> = {
  pending_match: '待匹配',
  sop_pending: 'SOP待制定',
  training: '训练中',
  awaiting_feedback: '待反馈',
  feedback_available: '可反馈',
  stage_complete: '阶段完成',
  closed: '已结案',
};

/** 列表筛选。契约 `GET /cases` 暂不支持按 display_status 筛，前端拉全量后客户端过滤。 */
export type CaseFilter = DisplayStatus | 'all';

export const CASE_FILTERS: { value: CaseFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'pending_match', label: '待匹配' },
  { value: 'sop_pending', label: 'SOP待制定' },
  { value: 'training', label: '训练中' },
  { value: 'awaiting_feedback', label: '待反馈' },
];

export type TaskStatus = components['schemas']['TrainingRecord']['status'];

/** 训练任务状态 → 中文，能力报告（训练记录）列表用。 */
export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  not_started: '未开始',
  in_progress: '进行中',
  paused: '已暂停',
  submitted: '已提交',
  changes_requested: '需修改',
  completed: '已完成',
  cancelled: '已取消',
};
