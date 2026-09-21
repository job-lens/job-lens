import type { components } from '@/shared/api/schema';

export type ResourceType = components['schemas']['Notification']['resource_type'];

export const RESOURCE_TYPE_LABELS: Record<ResourceType, string> = {
  task: '任务',
  submission: '提交',
  assistance: '求助',
  annotation: '标注',
  file: '文件',
  case: '个案',
};
