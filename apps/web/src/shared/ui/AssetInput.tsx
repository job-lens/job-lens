import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  api,
  ApiError,
  createHeaders,
  unwrap,
  unwrapVoid,
  updateHeaders,
} from '@/shared/api/client';
import type { components } from '@/shared/api/schema';
import styles from './AssetInput.module.css';

type Asset = components['schemas']['FileAsset'];
type Purpose = Asset['purpose'];
export function AssetInput({
  caseId,
  taskId,
  purpose,
  value,
  onChange,
  disabled = false,
}: {
  caseId: string;
  taskId?: string;
  purpose: Purpose;
  value: string[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
}) {
  const [pending, setPending] = useState<string[]>([]);
  const upload = useMutation({
    mutationFn: async (file: File) =>
      unwrap(
        await api.POST('/files', {
          params: { header: createHeaders(crypto.randomUUID()) },
          body: { case_id: caseId, task_id: taskId, purpose, file: file.name },
          bodySerializer(body) {
            const form = new FormData();
            form.set('case_id', body.case_id);
            form.set('purpose', body.purpose);
            if (body.task_id) form.set('task_id', body.task_id);
            form.set('file', file);
            return form;
          },
        }),
      ),
    onSuccess: asset => setPending(ids => [...ids, asset.id]),
  });
  const ids = [...new Set([...value, ...pending])];
  return (
    <div className={styles.group}>
      <label className={styles.picker}>
        选择图片或 PDF（最多 5 个，每个不超过 20 MB）
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,application/pdf"
          disabled={disabled || upload.isPending || ids.length >= 5}
          onChange={event => {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (file) upload.mutate(file);
          }}
        />
      </label>
      {upload.isPending && <p role="status">正在上传到私有文件区…</p>}
      {upload.isError && (
        <p role="alert">
          {upload.error instanceof ApiError ? upload.error.message : '上传未完成，请重试。'}
        </p>
      )}
      {ids.map(id => (
        <AssetRow
          key={id}
          id={id}
          disabled={disabled}
          ready={() => {
            if (!value.includes(id)) onChange([...value, id]);
          }}
          remove={() => {
            setPending(items => items.filter(item => item !== id));
            onChange(value.filter(item => item !== id));
          }}
        />
      ))}
    </div>
  );
}
function AssetRow({
  id,
  ready,
  remove,
  disabled,
}: {
  id: string;
  ready: () => void;
  remove: () => void;
  disabled: boolean;
}) {
  const file = useQuery({
    queryKey: ['file', id],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET('/files/{file_id}', { params: { path: { file_id: id } }, signal })),
    refetchInterval: query =>
      ['quarantined', 'scanning'].includes(query.state.data?.state ?? '') ? 2000 : false,
  });
  const deletion = useMutation({
    mutationFn: async () =>
      unwrapVoid(
        await api.DELETE('/files/{file_id}', {
          params: { path: { file_id: id }, header: updateHeaders(file.data!.version) },
        }),
      ),
    onSuccess: remove,
  });
  const asset = file.data;
  useEffect(() => {
    if (asset?.state === 'ready') ready();
  }, [asset?.state, ready]);
  if (!asset)
    return (
      <p role={file.isError ? 'alert' : 'status'}>
        {file.isError ? '文件信息未能加载' : '正在读取文件状态…'}
      </p>
    );
  const states = {
    quarantined: '等待安全检查',
    scanning: '正在检查',
    ready: '可以使用',
    rejected: '未通过检测',
    deleted: '已删除',
  };
  return (
    <div className={styles.row}>
      <div>
        <strong>{asset.filename}</strong>
        <span className={styles.meta}>
          {states[asset.state]} · {Math.ceil(asset.size_bytes / 1024)} KB
        </span>
        {asset.reason && <p role="alert">{asset.reason}</p>}
        {deletion.isError && (
          <p role="alert">
            {deletion.error instanceof ApiError ? deletion.error.message : '文件未能删除。'}
          </p>
        )}
      </div>
      <div className={styles.actions}>
        {asset.state === 'ready' && (
          <a
            className="qx-btn qx-btn--text"
            href={`/api/v1/files/${id}/content`}
            target="_blank"
            rel="noreferrer"
          >
            查看
          </a>
        )}
        <button
          className="qx-btn qx-btn--text"
          type="button"
          disabled={disabled || deletion.isPending}
          onClick={() => deletion.mutate()}
        >
          删除
        </button>
      </div>
    </div>
  );
}
