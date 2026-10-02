import type { ReactNode } from 'react';

/*
 * 七个预设角色，照 Grok Bot 的头像系统做：纯色平涂的几何身体 + 两只偏在一侧的斜胶囊眼。
 * 没有高光、腮红、阴影、描边、渐变，也不画嘴；所有表情和动作都靠眼睛在身体表面移动。
 * 眼睛偏在右上方，像在往旁边看，形状就有了朝向，这就是 2.5D 的来源，不要把眼睛挪回正中间。
 *
 * 少数角色带一点小装饰（耳朵、鼻头、天线），借鉴 oneworks 头像那种纯几何加一笔点缀的做法；
 * 装饰只用身体同色或眼睛的墨色，不另加颜色，也不要加到每个角色身上，否则就没有区分度了。
 *
 * 一个角色 = 轮廓 + 眼睛落点 + 颜色 + 可选装饰。以后让用户自定义，就是在角色和颜色两列里各挑一个。
 * 坐标系是 120×120 的 viewBox，身体大致居中在 (60, 62)。shape 是一条闭合路径。
 * look 是眼睛平视时两眼中点的位置；眼睛张望的活动范围由 AgentAvatar 统一控制。
 */
/* 共用的四种动作，具体表现见 agent-avatar.css */
export type AgentAvatarState = 'idle' | 'think' | 'work' | 'greet';
export const agentAvatarStates: readonly AgentAvatarState[] = ['idle', 'think', 'work', 'greet'];

export type AgentAvatarId = 'cheng' | 'nian' | 'qi' | 'shi' | 'heng' | 'ruo' | 'you';

export interface AgentAvatarPreset {
  readonly id: AgentAvatarId;
  readonly name: string;
  readonly shape: string;
  readonly look: { readonly x: number; readonly y: number };
  readonly color: string;
  /** 画在身体后面的装饰（耳朵、天线），转头时会反向小幅错开 */
  readonly behind?: () => ReactNode;
  /** 两眼下方的小鼻头，跟着眼睛一起移动 */
  readonly nose?: boolean;
}

function smoothRadial(cx: number, cy: number, radius: (theta: number) => number, samples = 48) {
  const points = Array.from({ length: samples }, (_, index) => {
    const theta = (index / samples) * Math.PI * 2 - Math.PI / 2;
    const r = radius(theta);
    return [cx + Math.cos(theta) * r, cy + Math.sin(theta) * r] as const;
  });
  const at = (index: number) => points[(index + samples) % samples];
  const f = (value: number) => value.toFixed(2);
  let d = `M${f(points[0][0])} ${f(points[0][1])}`;
  for (let index = 0; index < samples; index += 1) {
    const [x0, y0] = at(index - 1),
      [x1, y1] = at(index),
      [x2, y2] = at(index + 1),
      [x3, y3] = at(index + 2);
    d += ` C${f(x1 + (x2 - x0) / 6)} ${f(y1 + (y2 - y0) / 6)} ${f(x2 - (x3 - x1) / 6)} ${f(y2 - (y3 - y1) / 6)} ${f(x2)} ${f(y2)}`;
  }
  return `${d} Z`;
}

/* 圆角多边形：每个角用二次曲线切圆，radius 是切进去的长度 */
function roundedPolygon(points: readonly (readonly [number, number])[], radius: number) {
  const n = points.length;
  const f = (value: number) => value.toFixed(2);
  const parts: string[] = [];
  points.forEach((point, index) => {
    const prev = points[(index - 1 + n) % n],
      next = points[(index + 1) % n];
    const toward = (from: readonly [number, number], to: readonly [number, number]) => {
      const dx = to[0] - from[0],
        dy = to[1] - from[1],
        len = Math.hypot(dx, dy);
      return [from[0] + (dx / len) * radius, from[1] + (dy / len) * radius] as const;
    };
    const a = toward(point, prev),
      b = toward(point, next);
    parts.push(
      `${index === 0 ? 'M' : 'L'}${f(a[0])} ${f(a[1])} Q${f(point[0])} ${f(point[1])} ${f(b[0])} ${f(b[1])}`,
    );
  });
  return `${parts.join(' ')} Z`;
}

function scallop(cx: number, cy: number, n: number, d: number, r: number) {
  const half = Math.PI / n;
  const valley = d * Math.cos(half) + Math.sqrt(r * r - (d * Math.sin(half)) ** 2);
  const point = (index: number) => {
    const angle = index * 2 * half - Math.PI / 2;
    return `${(cx + Math.cos(angle) * valley).toFixed(2)} ${(cy + Math.sin(angle) * valley).toFixed(2)}`;
  };
  return `M${point(0)} ${Array.from({ length: n }, (_, index) => `A${r} ${r} 0 1 1 ${point(index + 1)}`).join(' ')} Z`;
}

const hexagon = Array.from({ length: 6 }, (_, index) => {
  const angle = (index / 6) * Math.PI * 2 - Math.PI / 2 + 0.18;
  return [60 + Math.cos(angle) * 34, 62 + Math.sin(angle) * 34] as const;
});

export const agentAvatarPresets: readonly AgentAvatarPreset[] = [
  {
    id: 'cheng',
    name: '澄',
    shape: 'M60 30 A32 32 0 1 1 60 94 A32 32 0 1 1 60 30 Z',
    look: { x: 68, y: 54 },
    color: '#5d8fe6',
    nose: true,
    /* 熊耳：小，耳根埋进头里将近一半；内耳略深一档，被头挡住一部分，读起来就是从头里长出来的 */
    behind: () => (
      <g>
        <circle cx="37.5" cy="41" r="10.5" fill="var(--aa-color)" />
        <circle cx="83.5" cy="41" r="10.5" fill="var(--aa-color)" />
        <circle cx="36" cy="39.5" r="5.2" className="aa-inner" />
        <circle cx="85" cy="39.5" r="5.2" className="aa-inner" />
      </g>
    ),
  },
  {
    id: 'nian',
    name: '念',
    shape: smoothRadial(60, 63, t => 30 + 4.5 * Math.cos(2 * (t - 0.35)) + 1.6 * Math.sin(3 * t)),
    look: { x: 68, y: 55 },
    color: '#ec8a52',
    nose: true,
    /* 猫耳：根部宽、往外斜，两个底角都落在头的轮廓里面，不会和头之间留缝 */
    behind: () => (
      <g>
        <path
          fill="var(--aa-color)"
          d={roundedPolygon(
            [
              [34, 54],
              [37, 19],
              [61, 41],
            ],
            5,
          )}
        />
        <path
          fill="var(--aa-color)"
          d={roundedPolygon(
            [
              [59, 41],
              [84, 18],
              [85, 53],
            ],
            5,
          )}
        />
        <path
          className="aa-inner"
          d={roundedPolygon(
            [
              [41, 42],
              [40, 27],
              [52, 38],
            ],
            3,
          )}
        />
        <path
          className="aa-inner"
          d={roundedPolygon(
            [
              [69, 37],
              [80, 26],
              [80, 41],
            ],
            3,
          )}
        />
      </g>
    ),
  },
  {
    id: 'qi',
    name: '栖',
    shape: 'M60 30 C86 30 92 36 92 62 C92 88 86 94 60 94 C34 94 28 88 28 62 C28 36 34 30 60 30 Z',
    look: { x: 69, y: 52 },
    color: '#3fae9c',
    nose: true,
    /* 熊猫耳：墨色，同样埋进头里一半 */
    behind: () => (
      <g className="aa-ink-fill">
        <circle cx="35" cy="37" r="11" />
        <circle cx="85" cy="37" r="11" />
      </g>
    ),
  },
  {
    id: 'shi',
    name: '拾',
    shape: 'M42 42 H78 A20 20 0 0 1 78 82 H42 A20 20 0 0 1 42 42 Z',
    look: { x: 71, y: 57 },
    color: '#e55f6f',
  },
  {
    id: 'heng',
    name: '恒',
    shape: roundedPolygon(
      [
        [60, 28],
        [96, 92],
        [24, 92],
      ],
      13,
    ),
    look: { x: 64, y: 70 },
    color: '#de6aa5',
  },
  {
    id: 'ruo',
    name: '若',
    shape: roundedPolygon(hexagon, 9),
    look: { x: 67, y: 55 },
    color: '#9a80e0',
    behind: () => (
      <g>
        <path d="M65 32 L68 16" stroke="var(--aa-color)" strokeWidth="3.4" strokeLinecap="round" />
        <circle cx="68.5" cy="13" r="5" fill="var(--aa-color)" />
      </g>
    ),
  },
  {
    id: 'you',
    name: '悠',
    shape: scallop(60, 63, 8, 23, 12.5),
    look: { x: 67, y: 57 },
    color: '#eeb146',
  },
];

export const agentAvatarById = Object.fromEntries(
  agentAvatarPresets.map(preset => [preset.id, preset]),
) as Record<AgentAvatarId, AgentAvatarPreset>;
