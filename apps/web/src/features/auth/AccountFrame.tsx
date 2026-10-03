import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Companions } from '@/shared/ui/Companions';
import { BrandMark } from '@/shared/ui/BrandMark';
import styles from './Auth.module.css';
export function AccountFrame({
  title,
  children,
  privateEntry = false,
}: {
  title: string;
  children: ReactNode;
  privateEntry?: boolean;
}) {
  return (
    <div className={styles.page}>
      <a className="skip-link" href="#account-main">
        跳到主要内容
      </a>
      <header className={styles.header}>
        <Link to="/" className={styles.brand}>
          <BrandMark />
          融职境
        </Link>
        <Link to="/" className="qx-btn qx-btn--ghost">
          返回首页
        </Link>
      </header>
      <main id="account-main" className={styles.content} tabIndex={-1}>
        <Companions privateEntry={privateEntry} />
        <h1 className="qx-display">{title}</h1>
        {children}
      </main>
    </div>
  );
}
