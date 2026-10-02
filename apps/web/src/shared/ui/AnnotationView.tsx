import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from './AsyncState';
import styles from './AnnotationView.module.css';

export function AnnotationView({ id }: { id: string }) {
  const annotation = useQuery({
    queryKey: ['annotation', id],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET('/annotations/{annotation_id}', {
          params: { path: { annotation_id: id } },
          signal,
        }),
      ),
  });
  if (annotation.isPending) return <LoadingState />;
  if (!annotation.data)
    return <ErrorPanel message="标注未能加载" retry={() => void annotation.refetch()} />;
  const item = annotation.data;
  return (
    <figure className={styles.figure}>
      <div className={styles.image}>
        <img
          src={`/api/v1/files/${item.asset_id}/content`}
          alt={item.kind === 'question' ? '提出问题的图片' : '辅导员指引图片'}
        />
        {item.markers.map((marker, index) => (
          <span
            key={marker.id}
            className={marker.shape === 'rect' ? styles.rect : styles.point}
            style={{
              left: `${marker.x * 100}%`,
              top: `${marker.y * 100}%`,
              width: marker.shape === 'rect' ? `${marker.width * 100}%` : undefined,
              height: marker.shape === 'rect' ? `${marker.height * 100}%` : undefined,
            }}
            aria-hidden="true"
          >
            {index + 1}
          </span>
        ))}
      </div>
      <figcaption>
        <ol>
          {item.markers.map(marker => (
            <li key={marker.id}>{marker.text}</li>
          ))}
        </ol>
      </figcaption>
    </figure>
  );
}
