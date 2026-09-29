import { Link } from 'react-router';
import type { components } from '@/shared/api/schema';
import styles from './counselor.module.css';

type CaseProfile = components['schemas']['CaseProfile'];

export function ProfileView({ profile, caseId }: { profile: CaseProfile; caseId: string }) {
  const p = profile.preferences;
  return (
    <section aria-label="个体画像" className={styles.card}>
      <h3>个体画像</h3>
      <dl className={styles.profileList}>
        <div className={styles.profileRow}>
          <dt>学员姓名</dt>
          <dd>{profile.display_name || '未填写'}</dd>
        </div>
        <div className={styles.profileRow}>
          <dt>学员编号</dt>
          <dd className={styles.mono}>{profile.user_id.slice(0, 8)}</dd>
        </div>
        <div className={styles.profileRow}>
          <dt>感官偏好</dt>
          <dd>
            {profile.sensory_preferences.length ? profile.sensory_preferences.join('、') : '未填写'}
          </dd>
        </div>
        <div className={styles.profileRow}>
          <dt>沟通方式</dt>
          <dd>{profile.communication_preference || '未填写'}</dd>
        </div>
        <div className={styles.profileRow}>
          <dt>工作备注</dt>
          <dd>{profile.work_notes || '未填写'}</dd>
        </div>
      </dl>

      <h4>个性化设置（学员已设，只读）</h4>
      <ul className={styles.prefList}>
        <li>字体大小：{p.font_scale}×</li>
        <li>音量：{Math.round(p.volume * 100)}%</li>
        <li>语音播报：{p.speech_enabled ? '开启' : '关闭'}</li>
        <li>震动提示：{p.vibration_enabled ? '开启' : '关闭'}</li>
        <li>安静模式：{p.quiet_mode ? '开启' : '关闭'}</li>
      </ul>

      <div className={styles.actions}>
        <a href="#match-title" className={styles.buttonLink}>
          发起匹配
        </a>
        <Link to={`/counselor/sop/${caseId}`} className={styles.buttonLink}>
          制定 SOP
        </Link>
        {/* 匹配度 / 能力报告属 M4（契约无能力评分），首版占位不显示。 */}
      </div>
    </section>
  );
}
