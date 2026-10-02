import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, unwrap, updateHeaders } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import styles from './profile.module.css';
type Profile = components['schemas']['Profile'];
type ProfileWrite = components['schemas']['ProfileWrite'];
function Fields({
  initial,
  onSaved,
  onReload,
}: {
  initial: Profile;
  onSaved: (value: Profile) => void;
  onReload: () => Promise<Profile>;
}) {
  const [base, setBase] = useState(initial);
  const [name, setName] = useState(initial.display_name);
  const [sensory, setSensory] = useState(initial.sensory_preferences.join('、'));
  const [communication, setCommunication] = useState(initial.communication_preference);
  const [work, setWork] = useState(initial.work_notes);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const save = useMutation({
    mutationFn: async (body: ProfileWrite) =>
      unwrap(
        await api.PUT('/me/profile', { params: { header: updateHeaders(base.version) }, body }),
      ),
    onSuccess: value => {
      setBase(value);
      onSaved(value);
      setStatus('资料已保存。');
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus('');
    save.mutate({
      display_name: name.trim(),
      sensory_preferences: sensory
        .split(/[、,，\n]/)
        .map(value => value.trim())
        .filter(Boolean),
      communication_preference: communication,
      work_notes: work,
    });
  }
  async function reload() {
    setLoading(true);
    setStatus('');
    try {
      const value = await onReload();
      setBase(value);
      setName(value.display_name);
      setSensory(value.sensory_preferences.join('、'));
      setCommunication(value.communication_preference);
      setWork(value.work_notes);
      save.reset();
    } finally {
      setLoading(false);
    }
  }
  const conflict = save.error instanceof ApiError && [412, 428].includes(save.error.status);
  return (
    <form className={styles.form} onSubmit={submit} aria-busy={save.isPending || loading}>
      <fieldset disabled={save.isPending || loading} className={styles.fields}>
        <label htmlFor="profile-name">
          怎么称呼你
          <input
            className="qx-input"
            id="profile-name"
            value={name}
            onChange={event => setName(event.target.value)}
            required
            maxLength={80}
            autoComplete="nickname"
          />
        </label>
        <label htmlFor="profile-communication">
          喜欢的沟通方式
          <input
            className="qx-input"
            id="profile-communication"
            value={communication}
            onChange={event => setCommunication(event.target.value)}
            maxLength={200}
            placeholder="例如：先用文字说明"
          />
        </label>
        <label htmlFor="profile-sensory">
          需要留意的感官偏好
          <input
            className="qx-input"
            id="profile-sensory"
            value={sensory}
            onChange={event => setSensory(event.target.value)}
            maxLength={410}
            placeholder="用顿号分开，最多 10 项"
          />
        </label>
        <label htmlFor="profile-work">
          希望辅导员了解的工作情况
          <textarea
            className="qx-textarea"
            id="profile-work"
            value={work}
            onChange={event => setWork(event.target.value)}
            rows={4}
            maxLength={1000}
          />
        </label>
      </fieldset>
      {save.error && (
        <div role="alert" className="qx-notice qx-notice--danger">
          <p>
            {conflict
              ? '资料有新版本。你的修改仍在这里，可以重新读取后再编辑。'
              : save.error instanceof ApiError
                ? save.error.message
                : '资料未保存，请重试。'}
          </p>
          {conflict && (
            <button
              className="qx-btn qx-btn--secondary"
              type="button"
              disabled={loading}
              onClick={() => void reload().catch(() => setStatus('重新读取失败，修改仍保留。'))}
            >
              重新读取最新资料
            </button>
          )}
        </div>
      )}
      {status && <p role="status">{status}</p>}
      <button className="qx-btn qx-btn--primary" type="submit" disabled={save.isPending || loading}>
        {save.isPending ? '正在保存…' : '保存资料'}
      </button>
    </form>
  );
}
export function ProfilePage() {
  const client = useQueryClient();
  const profile = useQuery({
    queryKey: ['profile'],
    queryFn: async ({ signal }) => unwrap(await api.GET('/me/profile', { signal })),
  });
  if (profile.isPending) return <LoadingState />;
  if (!profile.data)
    return <ErrorPanel message="个人资料暂不可用" retry={() => void profile.refetch()} />;
  async function reload() {
    const result = await profile.refetch();
    if (result.error) throw result.error;
    if (!result.data) throw new Error('Profile unavailable');
    return result.data;
  }
  function saved(value: Profile) {
    client.setQueryData(['profile'], value);
    client.setQueryData<components['schemas']['User']>(['session'], current =>
      current ? { ...current, display_name: value.display_name } : undefined,
    );
  }
  return (
    <section className={styles.page}>
      <header>
        <h1 className="qx-section-title">让支持更适合你</h1>
        <p>记录你希望辅导员了解的需要，之后可以随时修改。</p>
      </header>
      <Fields initial={profile.data} onSaved={saved} onReload={reload} />
    </section>
  );
}
