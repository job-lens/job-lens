import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, unwrap, updateHeaders } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import styles from './profile.module.css';
type Preferences = components['schemas']['Preferences'];
function SettingsForm({
  initial,
  onSaved,
  onReload,
}: {
  initial: Preferences;
  onSaved: (value: Preferences) => void;
  onReload: () => Promise<Preferences>;
}) {
  const [value, setValue] = useState(initial);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const save = useMutation({
    mutationFn: async () => {
      const { version, ...body } = value;
      return unwrap(
        await api.PUT('/me/preferences', { params: { header: updateHeaders(version) }, body }),
      );
    },
    onSuccess: result => {
      setValue(result);
      onSaved(result);
      setStatus('设置已保存。');
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus('');
    save.mutate();
  }
  async function reload() {
    setLoading(true);
    try {
      setValue(await onReload());
      save.reset();
      setStatus('已读取最新设置。');
    } catch {
      setStatus('重新读取失败，修改仍保留。');
    } finally {
      setLoading(false);
    }
  }
  const conflict = save.error instanceof ApiError && [412, 428].includes(save.error.status);
  return (
    <form className={styles.form} onSubmit={submit} aria-busy={save.isPending || loading}>
      <fieldset className={styles.fields} disabled={save.isPending || loading}>
        <label className={styles.toggle}>
          <span>
            安静模式<span className="qx-meta">暂停声音与震动，保留文字指引。</span>
          </span>
          <input
            type="checkbox"
            checked={value.quiet_mode}
            onChange={event => setValue({ ...value, quiet_mode: event.target.checked })}
          />
        </label>
        <label htmlFor="font-scale">
          文字大小
          <select
            className="qx-input"
            id="font-scale"
            value={value.font_scale}
            onChange={event =>
              setValue({
                ...value,
                font_scale: Number(event.target.value) as Preferences['font_scale'],
              })
            }
          >
            <option value={1}>标准</option>
            <option value={1.25}>较大</option>
            <option value={1.5}>更大</option>
          </select>
        </label>
        <label className={styles.toggle}>
          <span>语音指引</span>
          <input
            type="checkbox"
            checked={value.speech_enabled}
            onChange={event => setValue({ ...value, speech_enabled: event.target.checked })}
          />
        </label>
        <label htmlFor="volume">
          音量 · {Math.round(value.volume * 100)}%
          <input
            id="volume"
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={value.volume}
            onChange={event => setValue({ ...value, volume: Number(event.target.value) })}
          />
        </label>
        <label className={styles.toggle}>
          <span>震动提示</span>
          <input
            type="checkbox"
            checked={value.vibration_enabled}
            onChange={event => setValue({ ...value, vibration_enabled: event.target.checked })}
          />
        </label>
      </fieldset>
      {save.error && (
        <div role="alert" className="qx-notice qx-notice--danger">
          <p>
            {conflict
              ? '设置有新版本。你的修改仍保留，请读取最新版本后再保存。'
              : save.error instanceof ApiError
                ? save.error.message
                : '设置未保存，请重试。'}
          </p>
          {conflict && (
            <button
              type="button"
              className="qx-btn qx-btn--secondary"
              disabled={loading}
              onClick={() => void reload()}
            >
              重新读取最新设置
            </button>
          )}
        </div>
      )}
      {status && <p role="status">{status}</p>}
      <button className="qx-btn qx-btn--primary" type="submit" disabled={save.isPending || loading}>
        {save.isPending ? '正在保存…' : '保存设置'}
      </button>
    </form>
  );
}
export function PreferencesPage() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['preferences'],
    queryFn: async ({ signal }) => unwrap(await api.GET('/me/preferences', { signal })),
  });
  if (query.isPending) return <LoadingState />;
  if (!query.data) return <ErrorPanel message="设置暂不可用" retry={() => void query.refetch()} />;
  async function reload() {
    const result = await query.refetch();
    if (result.error) throw result.error;
    if (!result.data) throw new Error('Preferences unavailable');
    return result.data;
  }
  return (
    <section className={styles.page}>
      <header>
        <h1 className="qx-section-title">舒服一点的界面</h1>
        <p>选择文字、声音和提示方式。安静模式会优先关闭声音与震动。</p>
      </header>
      <SettingsForm
        initial={query.data}
        onSaved={value => client.setQueryData(['preferences'], value)}
        onReload={reload}
      />
    </section>
  );
}
