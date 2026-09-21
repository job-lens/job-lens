import { useParams } from 'react-router';
import { ApiError } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { FeedbackForm } from './FeedbackForm';
import { FeedbackView } from './FeedbackView';
import { useSubmission } from './queries';

export function FeedbackPage() {
  const { id } = useParams();
  if (!id) return <ErrorPanel message="缺少提交编号" />;
  return <FeedbackDetail submissionId={id} />;
}

function FeedbackDetail({ submissionId }: { submissionId: string }) {
  const submission = useSubmission(submissionId);

  if (submission.isPending) return <LoadingState />;
  if (submission.isError) {
    if (submission.error instanceof ApiError && submission.error.status === 404)
      return <ErrorPanel message="此提交不存在或您无权访问" />;
    return <ErrorPanel message="提交信息暂不可用" retry={() => void submission.refetch()} />;
  }
  if (!submission.data) return null;

  // 已有一份主反馈 → 只读展示；否则进入审核表单。
  return submission.data.feedback ? (
    <FeedbackView submission={submission.data} />
  ) : (
    <FeedbackForm submission={submission.data} />
  );
}
