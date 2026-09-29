import { useRef, useState, type MouseEvent } from 'react';
import { useCreateAnnotation } from './queries';
import styles from './training.module.css';

type DraftMarker = { x: number; y: number; text: string };

/**
 * 指引标注编辑器：在证据图片上点击放置标注点，填写说明后保存为指引标注草稿。
 * 坐标按图片渲染尺寸归一化到 [0,1]，与契约 PointMarker 的 x/y 一致。
 */
export function AnnotationEditor({
  taskId,
  submissionId,
  assetId,
  onCreated,
}: {
  taskId: string;
  submissionId: string | null;
  assetId: string;
  onCreated?: (annotationId: string) => void;
}) {
  const create = useCreateAnnotation(taskId);
  const [markers, setMarkers] = useState<DraftMarker[]>([]);
  const surfaceRef = useRef<HTMLDivElement>(null);

  function place(e: MouseEvent<HTMLDivElement>) {
    const el = surfaceRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const x = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height));
    setMarkers(prev => [...prev, { x, y, text: '' }]);
  }

  function setText(index: number, text: string) {
    setMarkers(prev => prev.map((m, i) => (i === index ? { ...m, text } : m)));
  }

  const ready = markers.some(m => m.text.trim() !== '');

  function save() {
    create.mutate(
      {
        asset_id: assetId,
        submission_id: submissionId,
        kind: 'guidance',
        markers: markers
          .filter(m => m.text.trim() !== '')
          .map(m => ({
            id: crypto.randomUUID(),
            x: m.x,
            y: m.y,
            text: m.text.trim(),
            shape: 'point' as const,
          })),
      },
      {
        onSuccess: created => {
          setMarkers([]);
          onCreated?.(created.id);
        },
      },
    );
  }

  return (
    <div className={styles.annotation}>
      <div
        ref={surfaceRef}
        className={styles.surface}
        role="img"
        aria-label="证据图片标注区"
        onClick={place}
      >
        <img
          className={styles.surfaceImg}
          src={`/api/v1/files/${assetId}/content`}
          alt="证据图片"
        />
        {markers.map((m, i) => (
          <span
            key={i}
            className={styles.markerDot}
            style={{ left: `${m.x * 100}%`, top: `${m.y * 100}%` }}
          />
        ))}
      </div>

      {markers.length > 0 && (
        <ol className={styles.markerList}>
          {markers.map((m, i) => (
            <li key={i} className={styles.markerRow}>
              <span className={styles.markerPos}>
                #{i + 1}（{Math.round(m.x * 100)}%, {Math.round(m.y * 100)}%）
              </span>
              <input
                aria-label={`标注 ${i + 1} 说明`}
                value={m.text}
                maxLength={200}
                placeholder="标注说明（1–200 字）"
                onChange={e => setText(i, e.target.value)}
              />
            </li>
          ))}
        </ol>
      )}

      <div className={styles.actions}>
        <button type="button" disabled={create.isPending || !ready} onClick={save}>
          保存指引标注
        </button>
      </div>
      {create.isError && (
        <p role="alert" className={styles.error}>
          保存标注失败，请重试
        </p>
      )}
    </div>
  );
}
