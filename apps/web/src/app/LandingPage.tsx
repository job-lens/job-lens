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
  ['了解需要', '沟通方式、感官偏好与工作目标。'],
  ['制定计划', '合适的任务，具体的操作步骤。'],
  ['执行提交', '逐步练习，整理并提交结果。'],
  ['反馈返工', '阅读建议，调整后再次练习。'],
];

function PaperIllustration({ step }: { step: number }) {
  return (
    <svg
      className={styles.paper}
      viewBox="0 0 320 170"
      role="img"
      aria-label="文件与清单的操作示意"
    >
      <path
        d="M35 47h84l12 12h58v78a10 10 0 0 1-10 10H45a10 10 0 0 1-10-10Z"
        fill="var(--qx-color-surface-strong)"
      />
      <g transform="rotate(-6 160 90)">
        <rect
          x="102"
          y="15"
          width="107"
          height="132"
          rx="8"
          fill="var(--qx-color-surface)"
          stroke="var(--qx-color-rule)"
        />
        <path
          d="M120 36h62M120 45h39"
          fill="none"
          stroke="var(--qx-color-rule-strong)"
          strokeWidth="3"
          strokeLinecap="round"
        />
        {[0, 1, 2].map(i => (
          <g key={i} transform={`translate(0 ${i * 26})`}>
            <rect
              x="119"
              y="61"
              width="12"
              height="12"
              rx="3"
              fill={i <= step ? 'var(--qx-color-data-olive)' : 'var(--qx-color-surface-strong)'}
            />
            {i <= step && (
              <path
                d="m122 67 2 2 4-5"
                fill="none"
                stroke="var(--qx-color-surface)"
                strokeWidth="1.5"
              />
            )}
            <path
              d="M142 65h48M142 72h29"
              fill="none"
              stroke="var(--qx-color-rule-strong)"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </g>
        ))}
      </g>
      <path
        d="M230 96h42m-9-9 9 9-9 9"
        fill="none"
        stroke="var(--qx-color-data-olive)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function TrainingPreview() {
  const [step, setStep] = useState(0);
  const current = demoSteps[step];
  return (
    <section id="experience" className={styles.experience} aria-label="文件整理任务示意">
      <header className={styles.previewHeader}>
        <span>我的训练 / 文件整理</span>
        <span className="qx-meta">交互示意</span>
      </header>
      <div className={styles.previewGrid}>
        <aside className={styles.outline}>
          <p>一次，做好一步。</p>
          <div role="group" aria-label="切换操作步骤示意" className={styles.steps}>
            {demoSteps.map((item, index) => (
              <button
                key={item.title}
                type="button"
                aria-label={item.title}
                aria-pressed={index === step}
                onClick={() => setStep(index)}
              >
                <span className={styles.stepNumber}>{index + 1}</span>
                <span>{item.title}</span>
                <span aria-hidden="true">{index < step ? '✓' : index === step ? '→' : ''}</span>
              </button>
            ))}
          </div>
          <p className={`qx-meta ${styles.exampleNote}`}>选择步骤，看看指引如何展开。</p>
        </aside>
        <div className={styles.instruction}>
          <div className={styles.instructionTitle}>
            <h2 className="qx-heading">{current.title}</h2>
            <span className="qx-meta">步骤示意 · {step + 1} / 3</span>
          </div>
          <PaperIllustration step={step} />
          <p aria-live="polite">{current.instruction}</p>
          <ul className={styles.checklist}>
            {current.lines.map(line => (
              <li key={line}>
                <span aria-hidden="true">✓</span>
                {line}
              </li>
            ))}
          </ul>
          <div className={styles.previewFoot}>
            <span className="qx-meta">可以停一停，也可以请求帮助。</span>
            <button
              className="qx-btn qx-btn--secondary"
              type="button"
              disabled={step === 2}
              onClick={() => setStep(step + 1)}
            >
              {step === 2 ? '示意已读完' : '看看下一步 →'}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
function RolePicture({ counselor = false }: { counselor?: boolean }) {
  return (
    <div className={styles.rolePicture} aria-hidden="true">
      <div className={styles.miniHeading}>{counselor ? '文件整理 · 审核' : '今天的训练'}</div>
      <div className={styles.miniRow}>
        <span className={styles.miniMark}>✓</span>
        <span>{counselor ? '已提交核对结果' : '核对文件名'}</span>
      </div>
      <div className={styles.miniRow}>
        <span className={styles.miniMark}>{counselor ? '↳' : '2'}</span>
        <span>{counselor ? '请补充清单中的日期' : '检查清单'}</span>
      </div>
      <div className={styles.miniLine} />
      <div className={styles.miniLine} />
    </div>
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
          <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
            <path
              d="M4 17V8h5v9m6 0V4h5v13M4 21h16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          融职境
        </Link>
        <nav aria-label="官网导航">
          <a className="qx-btn qx-btn--ghost" href="#experience">
            看看怎么用
          </a>
          <a className="qx-btn qx-btn--ghost" href="#journey">
            训练流程
          </a>
          <Link className="qx-btn qx-btn--secondary" to="/login">
            登录
          </Link>
        </nav>
      </header>
      <main id="main" tabIndex={-1}>
        <section className={styles.hero}>
          <Companions />
          <h1 className="qx-display" aria-label="让工作，有清楚的下一步。">
            让工作，有清楚的下一步。
          </h1>
          <p>为孤独症学员与辅导员，把工作训练变成一段有支持的日常。</p>
          <Link className="qx-btn qx-btn--primary qx-btn--lg" to="/login">
            登录并开始 <span aria-hidden="true">→</span>
          </Link>
        </section>
        <TrainingPreview />
        <section id="journey" className={styles.section} aria-label="训练流程">
          <div className={styles.sectionHeading}>
            <h2 className="qx-section-title">从了解你，到一起做好。</h2>
            <p>计划、练习与反馈，在同一条路径上。</p>
          </div>
          <ol className={styles.journeyList}>
            {journey.map(([title, body], i) => (
              <li key={title}>
                <span className={styles.journeyNumber}>{i + 1}</span>
                <h3 className="qx-heading">{title}</h3>
                <p>{body}</p>
              </li>
            ))}
          </ol>
        </section>
        <section id="roles" className={styles.roleSection} aria-label="使用角色">
          <article className={styles.role}>
            <RolePicture />
            <h2 className="qx-section-title">我来练习</h2>
            <p>看清当前一步。保存进度、提交结果，收到建议后继续调整。</p>
            <Link className="qx-btn qx-btn--secondary" to="/learner">
              进入学员工作台 →
            </Link>
          </article>
          <article className={styles.role}>
            <RolePicture counselor />
            <h2 className="qx-section-title">我来陪伴</h2>
            <p>了解学员需要，制定步骤。审核具体结果，把支持落在每一次反馈里。</p>
            <Link className="qx-btn qx-btn--secondary" to="/counselor">
              进入辅导员工作台 →
            </Link>
          </article>
        </section>
        <section className={styles.supportSection} aria-label="使用支持">
          <h2 className="qx-section-title">按照你的节奏来。</h2>
          <p>没有突然的声音，没有倒数催促。动效可以暂停，任务可以分步查看。</p>
          <div className={styles.supportTags}>
            <span>清楚的步骤</span>
            <span>具体的反馈</span>
            <span>可请求协助</span>
          </div>
        </section>
        <section className={styles.questions} aria-label="常见问题">
          <h2 className="qx-section-title">开始之前</h2>
          <div>
            <details>
              <summary>融职境适合谁？</summary>
              <p>
                面向需要分步工作训练的孤独症学员，以及为学员制定计划、审核训练结果的辅导员。具体训练安排由学员与辅导员共同讨论。
              </p>
            </details>
            <details>
              <summary>一次训练怎么完成？</summary>
              <p>
                辅导员先了解学员情况，确认任务与操作指引。学员依次练习并提交结果，辅导员审核后给出反馈；需要调整时可以返工、重新提交。
              </p>
            </details>
            <details>
              <summary>辅导员和学员看到的内容一样吗？</summary>
              <p>
                学员查看自己的计划和训练；辅导员查看已分配个案并管理指引与反馈。登录后按账号角色进入相应工作台。
              </p>
            </details>
            <details>
              <summary>这可以代替医疗或治疗服务吗？</summary>
              <p>
                融职境用于工作训练与协作，不提供诊断或治疗。涉及健康或治疗的问题，请咨询具备相应资质的专业人员。
              </p>
            </details>
          </div>
        </section>
      </main>
      <footer className={styles.footer}>
        <span>融职境 · Job Lens</span>
        <nav aria-label="页脚导航">
          <a href="#experience">产品体验</a>
          <Link to="/login">登录</Link>
          <a href="https://github.com/job-lens/job-lens">项目源码</a>
        </nav>
      </footer>
    </div>
  );
}
