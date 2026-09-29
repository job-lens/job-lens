import type { components } from '@/shared/api/schema';

export type AssistanceState = components['schemas']['Assistance']['state'];
export type PreferredMode = components['schemas']['Assistance']['preferred_mode'];

/** 求助状态 → 中文。辅导员端「交流」工作台与详情页共用。 */
export const ASSISTANCE_STATE_LABELS: Record<AssistanceState, string> = {
  queued: '待接单',
  accepted: '已接单',
  resolved: '已解决',
  cancelled: '已取消',
};

/** 求助首选沟通方式。 */
export const MODE_LABELS: Record<PreferredMode, string> = {
  text: '文字',
  annotation: '标注',
};
