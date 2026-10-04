import { useState } from 'react';
import { Link } from 'react-router';
import { WorkIllustration as PaperIllustration } from '@/shared/ui/WorkIllustration';
import { Buddy } from '@/shared/ui/Buddy';
import { Companions } from '@/shared/ui/Companions';
import { BrandMark } from '@/shared/ui/BrandMark';
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
const paces = [
  ['不催促', '没有倒计时，也没有突然弹出的提醒。做完一步，再看下一步。'],
  ['少刺激', '没有提示音，颜色克制。所有动效都可以一键暂停。'],
  ['说得清', '每条指引只讲一件事，用具体的词，不用比喻。'],
  ['随时求助', '卡住的时候可以直接请辅导员看一眼，不用等到交作业。'],
];
/* 与 paces 一一对应的线条图标：时钟、静音喇叭、两行文字、举手 */
const paceIcons = [
  'M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  'M4 9h3l5-4v14l-5-4H4ZM16 9l5 6M21 9l-5 6',
  'M5 8h14M5 12h10M5 16h12',
  'M8 13V6a1.5 1.5 0 0 1 3 0v5M11 11V4.5a1.5 1.5 0 0 1 3 0V11M14 11V6a1.5 1.5 0 0 1 3 0v7c0 4-2.5 7-6 7-2.5 0-4-1.5-5.5-4L4 13.5a1.5 1.5 0 0 1 2.5-1.6L8 14',
];

/*
 * 训练流程四步各配一张小界面，示意那一步在产品里大概长什么样。
 * 都是装饰（aria-hidden），信息以旁边的标题和说明为准。
 */
function JourneyVignette({ index }: { index: number }) {
  if (index === 0)
    return (
      <div className={styles.vignette} aria-hidden="true">
        <span className={styles.vLabel}>偏好</span>
        <div className={styles.vTags}>
          <span>文字说明</span>
          <span>安静环境</span>
          <span>分步查看</span>
        </div>
      </div>
    );
  if (index === 1)
    return (
      <div className={styles.vignette} aria-hidden="true">
        <span className={styles.vLabel}>文件整理 · 3 步</span>
        <div className={styles.vRows}>
          <i />
          <i />
          <i />
        </div>
      </div>
    );
  if (index === 2)
    return (
      <div className={styles.vignette} aria-hidden="true">
        <span className={styles.vLabel}>第 2 步 / 共 3 步</span>
        <div className={styles.vBar}>
          <i style={{ width: '66%' }} />
        </div>
        <span className={styles.vChip}>已保存</span>
      </div>
    );
  return (
    <div className={styles.vignette} aria-hidden="true">
      <span className={styles.vLabel}>辅导员</span>
      <p className={styles.vBubble}>日期那一栏再核对一次就好。</p>
    </div>
  );
}

/* 两种身份卡片里的工作台缩略图，同样只是示意 */
function RolePreview({ counselor = false }: { counselor?: boolean }) {
  return (
    <div className={styles.rolePreview} aria-hidden="true">
      {counselor ? (
        <>
          <span className={styles.vLabel}>待审核</span>
          {['文件整理 · 核对结果', '物品分类 · 第 2 步', '前台接待 · 练习记录'].map((t, i) => (
            <div key={t} className={styles.previewRow}>
              <span className={styles.previewDot} data-tone={i === 0 ? 'on' : 'off'} />
              <span>{t}</span>
              <span className={styles.previewMeta}>{i === 0 ? '新' : ''}</span>
            </div>
          ))}
        </>
      ) : (
        <>
          <span className={styles.vLabel}>今天的训练</span>
          <div className={styles.previewTask}>
            <strong>文件整理</strong>
            <span>第 2 步 · 检查清单</span>
            <div className={styles.vBar}>
              <i style={{ width: '40%' }} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
const questions = [
  [
    '融职境适合谁？',
    '面向需要分步工作训练的孤独症学员，以及为学员制定计划、审核训练结果的辅导员。具体训练安排由学员与辅导员共同讨论。',
  ],
  [
    '一次训练怎么完成？',
    '辅导员先了解学员情况，确认任务与操作指引。学员依次练习并提交结果，辅导员审核后给出反馈；需要调整时可以返工、重新提交。',
  ],
  [
    '辅导员和学员看到的内容一样吗？',
    '学员查看自己的计划和训练；辅导员查看已分配个案并管理指引与反馈。登录后按账号角色进入相应工作台。',
  ],
  [
    '这可以代替医疗或治疗服务吗？',
    '融职境用于工作训练与协作，不提供诊断或治疗。涉及健康或治疗的问题，请咨询具备相应资质的专业人员。',
  ],
];

/*
 * 首页的产品窗口：只是示意，不连接口、不出现「提交」按钮。
 * 测试按按钮名「核对文件名 / 检查清单 / 整理结果」和「步骤示意 · n / 3」找它，改文案时一起改。
 */
function TrainingPreview() {
  const [step, setStep] = useState(0);
  const current = demoSteps[step];
  return (
    <div className={styles.window} role="group" aria-label="文件整理任务示意">
      <div className={styles.windowBar}>
        <span>我的训练 · 文件整理</span>
        <span className="qx-meta">交互示意</span>
      </div>
      <div className={styles.windowBody}>
        <div role="group" aria-label="切换操作步骤示意" className={styles.steps}>
          {demoSteps.map((item, index) => (
            <button
              key={item.title}
              type="button"
              aria-label={item.title}
              aria-pressed={index === step}
              onClick={() => setStep(index)}
            >
              <span className={styles.stepNumber}>{index < step ? '✓' : index + 1}</span>
              <span>{item.title}</span>
            </button>
          ))}
        </div>
        <div className={styles.instruction}>
          <div className={styles.instructionTitle}>
            <h3>{current.title}</h3>
            <span className="qx-meta">步骤示意 · {step + 1} / 3</span>
          </div>
          <PaperIllustration step={step} />
          <p aria-live="polite">{current.instruction}</p>
          <ul className={styles.checklist}>
            {current.lines.map(line => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <div className={styles.windowFoot}>
            <span className="qx-meta">可以停一停，也可以请求帮助。</span>
            <button
              className="qx-btn qx-btn--secondary"
              type="button"
              disabled={step === 2}
              onClick={() => setStep(step + 1)}
            >
              {step === 2 ? '示意已读完' : '下一步 →'}
            </button>
          </div>
        </div>
      </div>
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
          <BrandMark />
          融职境
        </Link>
        <nav aria-label="官网导航" className={styles.nav}>
          <a href="#experience">看看怎么用</a>
          <a href="#journey">训练流程</a>
          <a href="#roles">两种身份</a>
        </nav>
        <Link className={styles.login} to="/login">
          登录 <span aria-hidden="true">↗</span>
        </Link>
      </header>

      <main id="main" tabIndex={-1}>
        <section className={styles.hero}>
          <h1 className={styles.headline} aria-label="让工作，有清楚的下一步。">
            <span className={styles.headlineLine}>
              让工作
              <span className={styles.inlineAvatar}>
                <Companions />
              </span>
              ，
            </span>
            <span className={styles.headlineLine}>有清楚的下一步。</span>
          </h1>
          <p className={styles.lede}>为孤独症学员与辅导员，把工作训练变成一段有支持的日常。</p>
          <Link className={styles.cta} to="/login">
            登录并开始 <span aria-hidden="true">→</span>
          </Link>
          <a className={styles.textLink} href="#experience">
            先看看一次训练长什么样 ↓
          </a>
        </section>

        <section className={styles.statement} aria-labelledby="statement-title">
          <h2 id="statement-title">
            <span>一次，</span>做好一步。
          </h2>
        </section>

        <section id="experience" className={styles.act} aria-labelledby="experience-title">
          <div className={styles.actHead}>
            <h2 id="experience-title">
              每一步，
              <br />
              都写清楚。
            </h2>
            <p>任务被拆成看得见的小步骤。当前这一步做什么、做到什么算完成，都摆在眼前，不用猜。</p>
          </div>
          <TrainingPreview />
        </section>

        <section id="journey" className={`${styles.act} ${styles.centered}`} aria-label="训练流程">
          <h2>从了解你，到一起做好。</h2>
          <p className={styles.actLede}>计划、练习与反馈，在同一条路径上。</p>
          <ol className={styles.journey}>
            {journey.map(([title, body], i) => (
              <li key={title}>
                <JourneyVignette index={i} />
                <span className={styles.journeyNumber}>{String(i + 1).padStart(2, '0')}</span>
                <h3>{title}</h3>
                <p>{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="roles" className={styles.act} aria-label="使用角色">
          <div className={styles.roles}>
            <article>
              <RolePreview />
              <h2>我来练习</h2>
              <p>看清当前一步。保存进度、提交结果，收到建议后继续调整。</p>
              <Link className={styles.textLink} to="/learner">
                进入学员工作台 →
              </Link>
            </article>
            <article>
              <RolePreview counselor />
              <h2>我来陪伴</h2>
              <p>了解学员需要，制定步骤。审核具体结果，把支持落在每一次反馈里。</p>
              <Link className={styles.textLink} to="/counselor">
                进入辅导员工作台 →
              </Link>
            </article>
          </div>
        </section>

        <section className={`${styles.act} ${styles.centered}`} aria-label="使用支持">
          <h2>按照你的节奏来。</h2>
          <p className={styles.actLede}>
            界面里每一处会动、会响、会催的地方，都先问一句：真的需要吗？
          </p>
          <ul className={styles.paceGrid}>
            {paces.map(([term, desc], i) => (
              <li key={term}>
                <span className={styles.paceIcon} aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="22" height="22">
                    <path d={paceIcons[i]} />
                  </svg>
                </span>
                <h3>{term}</h3>
                <p>{desc}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className={styles.questions} aria-label="常见问题">
          <h2>开始之前</h2>
          <div>
            {questions.map(([q, a]) => (
              <details key={q}>
                <summary>{q}</summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
        </section>

        <section className={styles.closing} aria-labelledby="closing-title">
          <div className={styles.closingAvatar} aria-hidden="true">
            <Buddy size={120} />
          </div>
          <h2 id="closing-title">今天，从第一步开始。</h2>
          <p className={styles.actLede}>学员和辅导员用各自的账号登录，进入自己的工作台。</p>
          <Link className={styles.cta} to="/login">
            登录 <span aria-hidden="true">→</span>
          </Link>
        </section>
      </main>

      <footer className={styles.footer}>
        <span className={styles.brand}>
          <BrandMark />
          融职境
        </span>
        <nav aria-label="页脚导航">
          <a href="/downloads/joblens-android-test.apk" download>
            安卓下载（测试版）
          </a>
          <a href="#experience">产品体验</a>
          <Link to="/login">登录</Link>
          <a href="https://github.com/job-lens/job-lens">项目源码</a>
        </nav>
      </footer>
    </div>
  );
}
