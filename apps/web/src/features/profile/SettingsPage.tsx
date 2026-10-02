import { Link, useSearchParams } from 'react-router';
import { SessionControls } from '@/features/auth/public';
import { Icon, type IconName } from '@/shared/ui/Icon';
import { ProfilePage } from './ProfileForm';
import { PreferencesPage } from './PreferencesPage';
import styles from './settings.module.css';

const sections = [
  { key: 'profile', label: '个人资料', description: '称呼与支持需求', icon: 'user' },
  { key: 'preferences', label: '阅读与提醒', description: '文字、声音与提示', icon: 'sound' },
  { key: 'security', label: '账户与安全', description: '登录与密码', icon: 'shield' },
] as const satisfies readonly { key: string; label: string; description: string; icon: IconName }[];
type Section = (typeof sections)[number]['key'];
function getSection(value: string | null): Section {
  return sections.some(item => item.key === value) ? (value as Section) : 'preferences';
}
export function SettingsPage() {
  const [params, setParams] = useSearchParams();
  const selected = getSection(params.get('tab'));
  function change(section: Section) {
    setParams({ tab: section });
  }
  return (
    <section className={styles.page}>
      <header className={styles.heading}>
        <h1>设置</h1>
        <p>调整个人资料和使用方式，让支持更适合你。</p>
      </header>
      <div className={styles.layout}>
        <nav className={styles.sections} aria-label="设置分类">
          {sections.map(item => (
            <button
              key={item.key}
              type="button"
              className={styles.sectionButton}
              aria-current={selected === item.key ? 'page' : undefined}
              onClick={() => change(item.key)}
            >
              <Icon name={item.icon} />
              <span>
                <strong>{item.label}</strong>
                <small>{item.description}</small>
              </span>
            </button>
          ))}
        </nav>
        <div className={styles.panel}>
          <div hidden={selected !== 'profile'}>
            <ProfilePage embedded />
          </div>
          <div hidden={selected !== 'preferences'}>
            <PreferencesPage embedded />
          </div>
          {selected === 'security' && (
            <section className={styles.security} aria-labelledby="security-title">
              <div>
                <h2 id="security-title">账户与安全</h2>
                <p>使用邮箱与密码登录，账户权限由平台管理。</p>
              </div>
              <div className={styles.securityRow}>
                <div>
                  <h3>重设密码</h3>
                  <p>通过注册邮箱接收一次性链接。重设后，所有旧登录会话都会退出。</p>
                </div>
                <Link to="/forgot-password" className="qx-btn qx-btn--secondary">
                  通过邮箱重设
                </Link>
              </div>
              <div className={styles.securityRow}>
                <div>
                  <h3>当前登录</h3>
                  <p>退出登录会撤销当前会话并清除本机的个人数据缓存。</p>
                </div>
                <SessionControls compact />
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}
