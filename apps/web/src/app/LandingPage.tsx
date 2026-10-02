import { useState } from 'react';
import { Link } from 'react-router';
import { Companions } from '@/shared/ui/Companions';
import styles from './LandingPage.module.css';

const demoSteps = [
  {
    title: '核对文件名',
    instruction: '把文件名和清单上的名称逐项对照。',
    lines: ['文件名称', '日期与编号', '对应的清单条目'],
  },
  {
    title: '检查清单',
    instruction: '沿着清单一项项检查，标出需要补充的内容。',
    lines: ['已核对的项目', '待补充的项目', '需要询问的项目'],
  },
  {
    title: '整理结果',
    instruction: '整理检查结果，交给辅导员查看并获得反馈。',
    lines: ['检查结果', '遇到的问题', '希望获得的帮助'],
  },
];
const journey = [
  ['了解需要', '记录沟通方式、感官偏好与工作目标。'],
  ['制定计划', '辅导员匹配任务，写下具体操作步骤。'],
  ['执行提交', '学员逐步练习，完成后提交结果。'],
  ['反馈返工', '辅导员审核，指出如何调整，再次练习。'],
];

function TrainingPreview() {
  const [step, setStep] = useState(0);
  const current = demoSteps[step];
  return (
    <section className={`${styles.preview} qx-card`} aria-label="文件整理任务示意">
      <header className={styles.previewHeader}>
        <h2 className="qx-heading">文件整理</h2>
        <span className="qx-meta">步骤示意 · {step + 1} / 3</span>
      </header>
      <div className={styles.document} aria-hidden="true">
        <svg width="76" height="94" viewBox="0 0 76 94">
          <path
            d="M12 4h35l17 17v66H12Z"
            fill="var(--qx-color-surface)"
            stroke="var(--qx-color-rule-strong)"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path
            d="M47 4v17h17M23 40h29M23 51h29M23 62h19"
            fill="none"
            stroke="var(--qx-color-ink-soft)"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
        <ul>
          {current.lines.map(line => (
            <li key={line}>
              <span>✓</span>
              {line}
            </li>
          ))}
        </ul>
      </div>
      <h3 className="qx-card__title">{current.title}</h3>
      <p className="qx-card__body">{current.instruction}</p>
      <div className={`${styles.steps} qx-segmented`} role="group" aria-label="切换操作步骤示意">
        {demoSteps.map((item, index) => (
          <button
            key={item.title}
            type="button"
            aria-label={item.title}
            aria-pressed={index === step}
            onClick={() => setStep(index)}
          >
            {index + 1}
            <span>{item.title}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

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
            训练流程
          </a>
          <a className="qx-btn qx-btn--ghost" href="#roles">
            使用角色
          </a>
          <Link className="qx-btn qx-btn--secondary" to="/login">
            登录
          </Link>
        </nav>
      </header>
      <main id="main" tabIndex={-1}>
        <section className={styles.hero}>
          <div className={styles.intro}>
            <Companions />
            <h1 className="qx-display" aria-label="让工作，有清楚的下一步。">
              让工作，
              <br />
              有清楚的下一步。
            </h1>
            <p>
              面向孤独症学员与辅导员的工作训练平台。
              <br />
              把任务拆开，按自己的节奏练习。
            </p>
            <Link className="qx-btn qx-btn--primary qx-btn--lg" to="/login">
              登录并开始 <span aria-hidden="true">→</span>
            </Link>
          </div>
          <TrainingPreview />
        </section>
        <section id="journey" className={styles.section} aria-label="训练流程">
          <h2 className="qx-section-title">一份任务，清楚走完</h2>
          <ol className={styles.journeyList}>
            {journey.map(([title, body], i) => (
              <li key={title}>
                <span className="qx-meta">0{i + 1}</span>
                <h3 className="qx-heading">{title}</h3>
                <p>{body}</p>
              </li>
            ))}
          </ol>
        </section>
        <section id="roles" className={styles.section}>
          <h2 className="qx-section-title">一起练习，各自清楚</h2>
          <div className={styles.roles}>
            <article>
              <h3 className="qx-heading">学员</h3>
              <p>查看自己的计划。一次只关注当前一步，遇到困难可以提出协助，提交后阅读具体反馈。</p>
              <Link className="qx-btn qx-btn--secondary" to="/learner">
                进入学员工作台 →
              </Link>
            </article>
            <article>
              <h3 className="qx-heading">辅导员</h3>
              <p>了解学员需要。制定匹配方案与操作指引，查看训练提交，把调整建议落到具体步骤。</p>
              <Link className="qx-btn qx-btn--secondary" to="/counselor">
                进入辅导员工作台 →
              </Link>
            </article>
          </div>
        </section>
        <section className={styles.section}>
          <h2 className="qx-section-title">支持，落在每一步里</h2>
          <div className={styles.support}>
            <article>
              <h3 className="qx-heading">步骤清楚</h3>
              <p>知道现在做什么，也知道接下来去哪里。</p>
            </article>
            <article>
              <h3 className="qx-heading">节奏由你</h3>
              <p>不催促，不制造突然的声音。小伙伴动效可以随时暂停。</p>
            </article>
            <article>
              <h3 className="qx-heading">反馈具体</h3>
              <p>把遇到的问题和下一次的调整联系起来。</p>
            </article>
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
