import styles from './WorkIllustration.module.css';

export function WorkIllustration({ step }: { step: number }) {
  return (
    <svg
      className={styles.scene}
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
