import { useEffect, useId, useRef, useState, type CSSProperties } from 'react';
import './Buddy.css';
import { useCompanionMotion } from './companionMotion';

/*
 * 融职境的陪伴角色「小融」：放在圆形头像框里的一个头像，头顶从框沿冒出来。
 * 骨架借 Everplain 官网的小平（2.5D 分层视差），人物是另一个人：深棕齐刘海短发、
 * 戴一副降噪耳机、细长竖眼、头顶一片小芽。耳机是有意的——它是很多孤独症学员
 * 日常真的会戴的东西，画在角色身上等于说"这样很正常"，别当装饰删掉。
 *
 * 2.5D：头拆成前后几层，转头时每层按 --dx/--dy 的深度平移，叠起来像脸在转。
 * --turn 左右（-1 看左，1 看右），--nod 上下。平移写在外层 g，循环动画写在里层 g。
 *
 * playing=false（用户暂停或系统减少动态）时不跟指针、不张望，只停在一个侧脸角度。
 * closed=true 时眼睛闭成弯线，登录页输密码用。
 */
export function Buddy({
  size = 150,
  label,
  playing = true,
  closed = false,
}: {
  size?: number;
  label?: string;
  playing?: boolean;
  closed?: boolean;
}) {
  const root = useRef<SVGSVGElement>(null);
  const motion = useCompanionMotion();
  const active = playing && motion.active;
  const [happy, setHappy] = useState(false);
  const uid = useId().replace(/:/g, '');
  const id = (name: string) => `jlb-${uid}-${name}`;

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    if (!active) {
      el.style.setProperty('--turn', '0.25');
      el.style.setProperty('--nod', '0');
      return;
    }
    let target = { turn: 0.2, nod: 0 };
    const current = { turn: 0.2, nod: 0 };
    let lastMove = 0;
    let frame = 0;
    const onMove = (event: PointerEvent) => {
      const box = el.getBoundingClientRect();
      target = {
        turn: Math.max(
          -1,
          Math.min(1, (event.clientX - box.left - box.width / 2) / (window.innerWidth * 0.45)),
        ),
        nod: Math.max(
          -1,
          Math.min(1, (event.clientY - box.top - box.height / 2) / (window.innerHeight * 0.6)),
        ),
      };
      lastMove = performance.now();
    };
    const tick = (now: number) => {
      if (now - lastMove > 4000) {
        // 没人理它时自己慢慢张望：两个周期叠一下，免得机械地左右摆
        target = {
          turn: Math.sin(now / 2600) * 0.6 + Math.sin(now / 1000) * 0.1,
          nod: Math.sin(now / 3400) * 0.3,
        };
      }
      current.turn += (target.turn - current.turn) * 0.06;
      current.nod += (target.nod - current.nod) * 0.06;
      el.style.setProperty('--turn', current.turn.toFixed(3));
      el.style.setProperty('--nod', current.nod.toFixed(3));
      frame = requestAnimationFrame(tick);
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    frame = requestAnimationFrame(tick);
    return () => {
      window.removeEventListener('pointermove', onMove);
      cancelAnimationFrame(frame);
    };
  }, [active]);

  useEffect(() => {
    if (!happy) return;
    const timer = window.setTimeout(() => setHappy(false), 1600);
    return () => window.clearTimeout(timer);
  }, [happy]);

  const layer = (dx: number, dy: number) => ({ '--dx': dx, '--dy': dy }) as CSSProperties;

  return (
    <svg
      ref={root}
      className="jl-buddy"
      data-mood={happy || closed ? 'happy' : 'idle'}
      data-playing={active}
      viewBox="0 -10 220 224"
      width={size}
      height={(size * 224) / 220}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      onClick={() => setHappy(true)}
      style={{ '--turn': 0.2, '--nod': 0 } as CSSProperties}
    >
      <defs>
        <radialGradient id={id('face')} cx="42%" cy="40%" r="70%">
          <stop offset="0%" stopColor="#fffaf5" />
          <stop offset="100%" stopColor="#f7e6d6" />
        </radialGradient>
        <linearGradient id={id('sleeve')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#82a6ee" />
          <stop offset="100%" stopColor="#5d8fe6" />
        </linearGradient>
        <linearGradient id={id('cup')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#f3eee6" />
          <stop offset="100%" stopColor="#d9cfc1" />
        </linearGradient>
        <linearGradient id={id('hair')} x1="0.3" y1="0" x2="0.7" y2="1">
          <stop offset="0%" stopColor="#6b5446" />
          <stop offset="100%" stopColor="#3f3029" />
        </linearGradient>
        <filter id={id('edge')} x="-20%" y="-30%" width="140%" height="160%">
          <feGaussianBlur stdDeviation="0.8" />
        </filter>
      </defs>

      {/* 脖子和毛衣肩膀：胸像式裁切，下沿交给头像框截掉。肩膀不跟着转头。 */}
      <rect x="88" y="166" width="26" height="24" rx="8" className="jlb-neck" />
      <path
        fill={`url(#${id('sleeve')})`}
        d="M34 220C36 194 62 182 101 182C140 182 166 194 168 220Z"
      />
      <path className="jlb-collar" d="M84 183C90 192 112 192 118 183" />
      <g className="jlb-bob">
        {/* 后发：齐下巴的短发，转头时反向移动拉出纵深 */}
        <g className="jlb-layer" style={layer(-6, -2)}>
          <path
            className="jlb-hair-back"
            d="M26 122C20 58 58 22 102 22C148 22 186 58 178 124C176 148 170 166 160 178L44 178C32 166 28 148 26 122Z"
          />
        </g>

        <g className="jlb-layer" style={layer(4, 1)}>
          <ellipse cx="101" cy="128" rx="56" ry="51" fill={`url(#${id('face')})`} />
        </g>

        <g className="jlb-layer" style={layer(8, 2)}>
          <ellipse
            className="jlb-blush"
            cx="66"
            cy="152"
            rx="9"
            ry="5"
            filter={`url(#${id('edge')})`}
          />
          <ellipse
            className="jlb-blush"
            cx="136"
            cy="152"
            rx="9"
            ry="5"
            filter={`url(#${id('edge')})`}
          />
        </g>

        {/* 眼睛：细长竖眼，平时偶尔眨一下；点一下变成笑眼 */}
        <g className="jlb-layer" style={layer(11, 5)}>
          <g className="jlb-eyes">
            <rect x="77" y="125" width="7.5" height="17" rx="3.75" />
            <rect x="117.5" y="125" width="7.5" height="17" rx="3.75" />
          </g>
          <g className="jlb-happy">
            <path d="M73 137Q80.5 131 88 137" />
            <path d="M114 137Q121.5 131 129 137" />
          </g>
          <path className="jlb-mouth" d="M98 153q3 2.2 6 0" />
        </g>

        {/* 齐刘海，右边分一道缝 */}
        <g className="jlb-layer" style={layer(6, 1)}>
          <g className="jlb-fringe">
            <path
              className="jlb-hair"
              fill={`url(#${id('hair')})`}
              d="M40 114C34 62 64 36 102 36C142 36 170 62 164 114C156 106 150 100 144 90C138 102 128 106 120 104C104 108 82 108 66 104C56 106 48 110 40 114Z"
            />
            <path
              className="jlb-hair-shade"
              d="M126 60C134 72 140 84 143 92C138 98 132 101 124 102C128 88 128 74 126 60Z"
            />
          </g>
        </g>

        {/* 降噪耳机：头梁从发顶绕过，耳罩扣在两侧 */}
        <g className="jlb-layer" style={layer(5, 0)}>
          <path className="jlb-band" d="M30 118C26 56 62 26 102 26C144 26 178 56 172 118" />
          <rect x="16" y="104" width="26" height="46" rx="13" fill={`url(#${id('cup')})`} />
          <rect className="jlb-cup-pad" x="34" y="110" width="9" height="34" rx="4.5" />
          <rect x="160" y="104" width="26" height="46" rx="13" fill={`url(#${id('cup')})`} />
          <rect className="jlb-cup-pad" x="159" y="110" width="9" height="34" rx="4.5" />
        </g>
      </g>
    </svg>
  );
}
