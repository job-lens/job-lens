import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { ApiError } from '@/shared/api/client';
import { Buddy } from '@/shared/ui/Buddy';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { AssistanceDetail } from './AssistancePage';
import { ASSISTANCE_STATE_LABELS } from './labels';
import { useAssistanceRequests, useCreateAssistance } from './queries';
import styles from './support.module.css';

export function SupportPage() {
  const { id } = useParams();
  if (!id) return <ErrorPanel message="缺少个案编号" />;
  return <LearnerSupport key={id} caseId={id} />;
}
function LearnerSupport({ caseId }: { caseId: string }) {
  const [params] = useSearchParams();
  const requests = useAssistanceRequests(undefined, caseId);
  const create = useCreateAssistance();
  const [message, setMessage] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const taskId = params.get('task');
  const stepId = params.get('step');
  const active = requests.data?.items.find(
    request => request.task_id === taskId && ['queued', 'accepted'].includes(request.state),
  );
  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <h1>需要帮助时，我们一起看。</h1>
        <Link
          to={taskId ? `/learner/tasks/${taskId}` : '/learner'}
          className="qx-btn qx-btn--secondary"
        >
          返回任务
        </Link>
      </header>
      {requests.isPending ? (
        <LoadingState />
      ) : !requests.data ? (
        <ErrorPanel message="求助记录未能加载" retry={() => void requests.refetch()} />
      ) : (
        <>
          {!active && (
            <form
              className={styles.card}
              onSubmit={event => {
                event.preventDefault();
                create.mutate(
                  {
                    case_id: caseId,
                    task_id: taskId,
                    step_id: stepId,
                    message: message.trim(),
                    attachment_ids: [],
                    preferred_mode: 'text',
                  },
                  {
                    onSuccess: value => {
                      setSelected(value.id);
                      setMessage('');
                    },
                  },
                );
              }}
            >
              <Buddy size={72} />
              <p className={styles.empty}>写下你需要帮助的地方。发送后，辅导员会在这里回复。</p>
              <textarea
                aria-label="需要什么帮助"
                maxLength={500}
                required
                value={message}
                disabled={create.isPending}
                onChange={event => setMessage(event.target.value)}
                placeholder="哪一步让你有点困惑？"
              />
              <button
                className="qx-btn qx-btn--primary"
                disabled={create.isPending || !message.trim()}
              >
                {create.isPending ? '正在发送…' : '发送求助'}
              </button>
              {create.isError && (
                <p role="alert">
                  {create.error instanceof ApiError
                    ? create.error.message
                    : '求助未能发送，请重试。'}
                </p>
              )}
            </form>
          )}
          {(selected ?? active?.id) && (
            <AssistanceDetail
              key={selected ?? active?.id}
              requestId={(selected ?? active?.id)!}
              learner
            />
          )}
          <h2>求助记录</h2>
          <ul className={styles.list}>
            {requests.data.items.map(request => (
              <li key={request.id}>
                <button
                  className="qx-btn qx-btn--secondary"
                  onClick={() => setSelected(request.id)}
                >
                  {ASSISTANCE_STATE_LABELS[request.state]} · {request.message}
                </button>
              </li>
            ))}
          </ul>
          {!requests.data.items.length && <p className={styles.empty}>还没有求助记录。</p>}
        </>
      )}
    </section>
  );
}
