import { Link } from 'react-router';
import { Companions } from '@/shared/ui/Companions';
import styles from './LandingPage.module.css';

const journey = [
  ['了解自己', '说出你的需要'],
  ['制定计划', '和辅导员一起'],
  ['分步练习', '一次做好一步'],
  ['收到反馈', '调整，再试一次'],
];

export function LandingPage() {
  return (
    <div className={styles.page}>
      <a className="skip-link" href="#main">
        跳到主要内容
      </a>
      <header className={styles.header}>
        <Link className={styles.brand} to="/" aria-label="融职境首页">
          融职境
        </Link>
        <nav aria-label="官网导航">
          <a className="qx-btn qx-btn--ghost" href="#journey">
            如何使用
          </a>
          <Link className="qx-btn qx-btn--secondary" to="/login">
            登录
          </Link>
        </nav>
      </header>
      <main id="main" tabIndex={-1}>
        <section className={styles.hero}>
          <Companions />
          <h1 className="qx-display">慢慢来，一起完成。</h1>
          <p>把工作拆成小步骤，按自己的节奏练习。</p>
          <Link className="qx-btn qx-btn--primary qx-btn--lg" to="/login">
            登录并开始 <span aria-hidden="true">→</span>
          </Link>
        </section>
        <section id="journey" className={styles.journey} aria-label="训练流程">
          <ol className={styles.journeyList}>
            {journey.map(([title, body], i) => (
              <li key={title}>
                <span className="qx-meta">0{i + 1}</span>
                <h2 className="qx-heading">{title}</h2>
                <p className="qx-meta">{body}</p>
              </li>
            ))}
          </ol>
          <div className={styles.roles}>
            <Link className="qx-btn qx-btn--ghost" to="/learner">
              学员工作台 →
            </Link>
            <Link className="qx-btn qx-btn--ghost" to="/counselor">
              辅导员工作台 →
            </Link>
          </div>
        </section>
      </main>
      <footer className={`${styles.footer} qx-meta`}>
        <span>融职境 · Job Lens</span>
        <a href="https://github.com/job-lens/job-lens">项目源码</a>
      </footer>
    </div>
  );
}
