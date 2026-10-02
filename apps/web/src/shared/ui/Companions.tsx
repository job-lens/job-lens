/** Original, quiet companions. Static by default: no sound, autonomous motion or flashing. */
export function Companions() {
  return (
    <svg
      width="204"
      height="88"
      viewBox="0 0 204 88"
      role="img"
      aria-label="三个安静相伴的小机器人"
    >
      <g fill="var(--qx-color-data-amber)">
        <path d="M17 67v8m31-8v8" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
        <rect x="7" y="30" width="52" height="41" rx="19" />
        <path
          d="m8 50-5 7m56-7 5 7"
          stroke="var(--qx-color-data-amber)"
          strokeWidth="6"
          strokeLinecap="round"
        />
        <rect x="14" y="37" width="38" height="23" rx="11" fill="var(--qx-color-surface)" />
        <path
          d="M25 46v4m15-4v4"
          stroke="var(--qx-color-ink)"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <path
          d="M29 54q4 3 8 0"
          fill="none"
          stroke="var(--qx-color-ink)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </g>
      <g fill="var(--qx-color-data-blue)">
        <path d="M86 69v8m29-8v8" stroke="currentColor" strokeWidth="7" strokeLinecap="round" />
        <rect x="77" y="46" width="49" height="27" rx="14" />
        <path
          d="m78 57-8 4m56-8 6-7"
          stroke="var(--qx-color-data-blue)"
          strokeWidth="7"
          strokeLinecap="round"
        />
        <path
          d="M99 15v7"
          stroke="var(--qx-color-data-blue)"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx="99" cy="13" r="4" />
        <rect x="71" y="22" width="61" height="37" rx="15" />
        <rect x="79" y="29" width="45" height="23" rx="9" fill="var(--qx-color-ink)" />
        <path
          d="M92 38v5m19-5v5"
          stroke="var(--qx-color-surface)"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx="102" cy="66" r="3" fill="var(--qx-color-surface)" />
      </g>
      <g fill="var(--qx-color-data-green)">
        <path d="M157 66v9m30-9v9" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
        <path d="M145 52c0-15 10-27 26-27s27 12 27 27v8c0 11-9 15-27 15s-26-4-26-15Z" />
        <path
          d="m146 52-5-5m56 5 4-6"
          stroke="var(--qx-color-data-green)"
          strokeWidth="6"
          strokeLinecap="round"
        />
        <rect x="153" y="39" width="36" height="22" rx="11" fill="var(--qx-color-surface)" />
        <path
          d="m161 48 3-2 3 2m10 0 3-2 3 2"
          fill="none"
          stroke="var(--qx-color-ink)"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d="M168 54q4 3 8 0"
          fill="none"
          stroke="var(--qx-color-ink)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </g>
    </svg>
  );
}
