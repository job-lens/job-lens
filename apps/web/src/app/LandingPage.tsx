import { Link } from 'react-router';
import styles from './LandingPage.module.css';

const journey = [
  ['了解你的需要', '记录沟通方式、感官偏好与工作目标，让支持从你的实际情况开始。'],
  ['一起制定计划', '辅导员结合资料确定训练方向，把任务拆成清晰的操作步骤。'],
  ['按自己的节奏练习', '一次专注一个步骤，查看指引，完成后提交；需要时可以暂停。'],
  ['收到反馈，再做调整', '辅导员审核提交并给出具体反馈，学员根据建议继续练习。'],
];

export function LandingPage() {
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
            <h1>把工作任务，变成能完成的每一步。</h1>
            <p>
              融职境为需要就业支持的学员与辅导员提供共同的训练空间。从了解个人需要开始，让计划、操作和反馈连接起来。
            </p>
            <Link className={styles.primary} to="/login">
              登录并开始 <span aria-hidden="true">↗</span>
            </Link>
          </div>
          <aside className={styles.preview} aria-label="分步任务示例">
            <div className={styles.previewTop}>
              <span>任务示例</span>
              <span>第 2 步 / 共 3 步</span>
            </div>
            <h2>整理一份工作清单</h2>
            <ol className={styles.steps}>
              <li>
                <span aria-hidden="true">✓</span>
                <div>
                  准备材料<small>先把需要的信息放在一起</small>
                </div>
              </li>
              <li className={styles.current}>
                <span aria-hidden="true">2</span>
                <div>
                  核对清单<small>逐项检查名称和数量</small>
                </div>
              </li>
              <li>
                <span aria-hidden="true">3</span>
                <div>
                  整理并提交<small>完成后等待辅导员反馈</small>
                </div>
              </li>
            </ol>
            <p className={styles.previewNote}>把注意力放在眼前这一步。</p>
          </aside>
        </section>
        <section id="journey" className={styles.journey}>
          <h2>从了解自己，到完成任务</h2>
          <ol className={styles.journeyList}>
            {journey.map(([title, body], i) => (
              <li key={title}>
                <span className={styles.number}>{i + 1}</span>
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
