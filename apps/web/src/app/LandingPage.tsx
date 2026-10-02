import { useState } from 'react';
import { Link } from 'react-router';
import styles from './LandingPage.module.css';

const journey = [
  ['了解你的需要', '告诉辅导员你的沟通方式、感官偏好和工作目标。'],
  ['一起制定计划', '确定训练方向，把任务拆成具体的操作步骤。'],
  ['按自己的节奏练习', '看指引，做完当前步骤。需要时可以暂停。'],
  ['收到反馈，再做调整', '提交后收到具体建议，调整方法，再练一次。'],
];

export function LandingPage() {
  const [motion, setMotion] = useState(
    () => !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  return (
    <div className={styles.page}>
      <a className="skip-link" href="#main">
        跳到主要内容
      </a>
      <header className={styles.header}>
        <Link className={styles.brand} to="/" aria-label="融职境首页">
          融职境 <span>Job Lens</span>
        </Link>
        <nav aria-label="官网导航">
          <a href="#journey">如何使用</a>
          <a href="#people">为谁提供支持</a>
          <Link to="/login">登录</Link>
        </nav>
      </header>
      <main id="main" tabIndex={-1}>
        <section className={styles.hero}>
          <div className={styles.intro}>
            <h1 aria-label="把工作任务，变成能完成的每一步。">
              把工作任务，
              <br />
              变成能完成的每一步。
            </h1>
            <p>和辅导员一起，把工作任务拆开。看清指引，按自己的节奏练习，再根据反馈继续。</p>
            <Link className={styles.primary} to="/login">
              登录并开始 <span aria-hidden="true">↗</span>
            </Link>
          </div>
          <figure className={styles.scene} data-motion={motion ? 'on' : 'off'}>
            <img
              className={styles.illustration}
              src="/illustrations/step-companion.svg"
              width="680"
              height="540"
              alt="机器人陪你把任务拆成清楚的步骤"
            />
            <figcaption>一次专注一件事，每一步都有指引。</figcaption>
            <button
              className={styles.motion}
              type="button"
              aria-pressed={motion}
              onClick={() => setMotion(!motion)}
            >
              {motion ? '关闭角色动效' : '开启角色动效'}
            </button>
          </figure>
        </section>
        <section id="journey" className={styles.journey}>
          <h2>从了解自己，到完成任务</h2>
          <ol className={styles.journeyList}>
            {journey.map(([title, body], i) => (
              <li key={title}>
                <img
                  className={styles.journeyImage}
                  src={`/illustrations/journey-${['profile', 'plan', 'practice', 'feedback'][i]}.svg`}
                  width="170"
                  height="130"
                  alt=""
                  loading="lazy"
                />
                <span className={styles.number}>第 {i + 1} 步</span>
                <h3>{title}</h3>
                <p>{body}</p>
              </li>
            ))}
          </ol>
        </section>
        <section id="people" className={styles.people}>
          <h2>同一个计划，各自清楚下一步</h2>
          <div className={styles.peopleGrid}>
            <article>
              <h3>学员</h3>
              <p>表达自己的需要，查看分步任务，记录练习进度，阅读辅导员的反馈。</p>
              <Link to="/learner">
                进入学员工作台 <span aria-hidden="true">→</span>
              </Link>
            </article>
            <article>
              <h3>辅导员</h3>
              <p>了解学员资料，制定支持方案和操作指引，审核提交，给出可执行的建议。</p>
              <Link to="/counselor">
                进入辅导员工作台 <span aria-hidden="true">→</span>
              </Link>
            </article>
          </div>
          <p className={styles.note}>
            工作台需要登录。辅导员权限由认证后取得，注册账号不会自动获得辅导员权限。
          </p>
        </section>
      </main>
      <footer className={styles.footer}>
        <span>融职境 · Job Lens</span>
        <a href="https://github.com/job-lens/job-lens">项目源码</a>
      </footer>
    </div>
  );
}
