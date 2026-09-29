import { useState } from 'react';
import { useParams } from 'react-router';
import { ApiError } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { ASSISTANCE_STATE_LABELS, MODE_LABELS } from './labels';
import {
  useAssistance,
  useAssistanceAction,
  useAssistanceMessages,
  useSendMessage,
} from './queries';
import styles from './support.module.css';

type ThreadMessage = {
  id: string;
  body: string;
  created_at: string;
};

/** 单个求助详情：求助原文 + 沟通记录 + 接单/解决 + 回复。 */
export function AssistancePage() {
  const { id } = useParams();
  if (!id) return <ErrorPanel message="缺少求助编号" />;
  return <AssistanceDetail requestId={id} />;
}

function AssistanceDetail({ requestId }: { requestId: string }) {
  const assistance = useAssistance(requestId);
  const messages = useAssistanceMessages(requestId);
  const action = useAssistanceAction(requestId);
  const send = useSendMessage(requestId);
  const [draft, setDraft] = useState('');

  if (assistance.isPending || messages.isPending) return <LoadingState />;
  if (assistance.isError || messages.isError) {
    const err = assistance.error ?? messages.error;
    if (err instanceof ApiError && err.status === 404)
      return <ErrorPanel message="此求助不存在或您无权访问" />;
    return (
      <ErrorPanel
        message="求助信息暂不可用"
        retry={() => {
          void assistance.refetch();
          void messages.refetch();
        }}
      />
    );
  }
  const req = assistance.data;
  // 契约里 SupportMessage 因 anyOf 合并被 openapi-typescript 生成了联合类型，
  // 但运行时字段恒定（id/body/created_at 均必填），这里收窄到展示所需字段。
  const thread = (messages.data?.items ?? []) as unknown as ThreadMessage[];
  if (!req) return null;

  const closed = req.state === 'resolved' || req.state === 'cancelled';
  const busy = action.isPending || send.isPending;

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <h2>求助详情</h2>
        <span className={styles.badge}>{ASSISTANCE_STATE_LABELS[req.state]}</span>
        <span className={styles.badge}>{MODE_LABELS[req.preferred_mode]}</span>
      </header>

      <p className={styles.original}>{req.message}</p>

      <h3>沟通记录</h3>
      {thread.length === 0 ? (
        <p className={styles.empty}>还没有消息</p>
      ) : (
        <ul className={styles.thread}>
          {thread.map(m => (
            <li key={m.id} className={styles.msg}>
              <span className={styles.msgMeta}>{new Date(m.created_at).toLocaleString()}</span>
              <p className={styles.msgBody}>{m.body}</p>
            </li>
          ))}
        </ul>
      )}

      {!closed && (
        <>
          <div className={styles.actions}>
            {req.state === 'queued' && (
              <button
                type="button"
                disabled={busy}
                onClick={() => action.mutate({ action: 'accept', version: req.version })}
              >
                接单
              </button>
            )}
            {req.state === 'accepted' && (
              <button
                type="button"
                disabled={busy}
                onClick={() => action.mutate({ action: 'resolve', version: req.version })}
              >
                标记已解决
              </button>
            )}
          </div>
          {action.isError && (
            <p role="alert" className={styles.error}>
              {action.error instanceof ApiError && action.error.status === 412
                ? '内容已被他人修改，请刷新后重试'
                : '操作失败，请重试'}
            </p>
          )}

          <form
            className={styles.form}
            onSubmit={e => {
              e.preventDefault();
              if (!draft.trim()) return;
              send.mutate(draft.trim(), { onSuccess: () => setDraft('') });
            }}
          >
            <textarea
              aria-label="回复内容"
              value={draft}
              maxLength={2000}
              placeholder="输入回复…"
              onChange={e => setDraft(e.target.value)}
            />
            <button type="submit" disabled={busy || !draft.trim()}>
              发送
            </button>
          </form>
          {send.isError && (
            <p role="alert" className={styles.error}>
              发送失败，请重试
            </p>
          )}
        </>
      )}
    </section>
  );
}
