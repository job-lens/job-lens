import { useParams } from 'react-router';
import { ApiError } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { MatchEditor } from './MatchEditor';
import { ProfileView } from './ProfileView';
import { RecordsView } from './RecordsView';
import { useCase, useCaseProfile } from './queries';
import { DISPLAY_STATUS_LABELS } from './status';
import styles from './counselor.module.css';

export function CasePage() {
  const { id } = useParams();
  if (!id) return <ErrorPanel message="缺少个案编号" />;
  return <CaseDetail caseId={id} />;
}

function CaseDetail({ caseId }: { caseId: string }) {
  const kase = useCase(caseId);
  const profile = useCaseProfile(caseId);

  if (kase.isPending || profile.isPending) return <LoadingState />;
  if (kase.isError || profile.isError) {
    const err = kase.error ?? profile.error;
    if (err instanceof ApiError && err.status === 404)
      return <ErrorPanel message="此个案不存在或您无权访问" />;
    return (
      <ErrorPanel
        message="个案信息暂不可用"
        retry={() => {
          void kase.refetch();
          void profile.refetch();
        }}
      />
    );
  }
  if (!kase.data || !profile.data) return null;

  return (
    <div className={styles.casePage}>
      <header>
        <h2>{profile.data.display_name || '未填写姓名'}</h2>
        <span className={styles.badge}>{DISPLAY_STATUS_LABELS[kase.data.display_status]}</span>
      </header>
      <ProfileView profile={profile.data} caseId={caseId} />
      <MatchEditor caseId={caseId} />
      <RecordsView caseId={caseId} />
    </div>
  );
}
