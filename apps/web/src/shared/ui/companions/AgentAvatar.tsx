import type { CSSProperties } from 'react';
import { agentAvatarById, type AgentAvatarId, type AgentAvatarState } from './avatars';
import './agent-avatar.css';

/*
 * 所有角色共用的动作，由根节点的 data-state 切换，全部是 CSS：
 * idle  待机：眼睛满脸张望，往左看时斜度跟着翻过来，隔几秒眨一次；
 * think 思考：眼睛飘到上方慢慢转，身体微微歪；
 * work  工作：眼睛低下去，一行一行左右扫，身体小幅快颠；
 * greet 打招呼：笑眼，蹦一下。
 *
 * 2.5D 只靠眼睛：--aa-turn 是视线左右（0 是默认的右上方，-1 是看向左边），--aa-nod 是上下（低头为正）。
 * 眼睛在身体表面移动、斜度翻转，身体跟着轻轻斜切，看起来就是转了个头。
 */

interface AgentAvatarProps {
  readonly avatar: AgentAvatarId;
  /** 覆盖角色的默认颜色 */
  readonly color?: string;
  readonly state?: AgentAvatarState;
  readonly size?: number | string;
  /** 给读屏用的名字；不传则视为装饰图，对读屏隐藏 */
  readonly label?: string;
  /** 动画错开的秒数，多个角色同屏时避免齐刷刷一起眨眼、一起转头 */
  readonly offset?: number;
  /** false 时暂停所有动画，例如还没滚到视口里 */
  readonly playing?: boolean;
  readonly className?: string;
}

export function AgentAvatar({
  avatar,
  color,
  state = 'idle',
  size = 96,
  label,
  offset = 0,
  playing = true,
  className,
}: AgentAvatarProps) {
  const preset = agentAvatarById[avatar];
  const style = {
    '--aa-color': color ?? preset.color,
    '--aa-offset': `${-offset}s`,
    width: size,
    height: size,
  } as CSSProperties;
  const labelled = Boolean(label);
  return (
    <svg
      className={['agent-avatar', className].filter(Boolean).join(' ')}
      viewBox="0 0 120 120"
      data-avatar={avatar}
      data-state={state}
      data-playing={playing ? 'true' : 'false'}
      role={labelled ? 'img' : undefined}
      aria-label={label}
      aria-hidden={labelled ? undefined : true}
      style={style}
    >
      <g className="aa-head">
        {preset.behind && <g className="aa-behind">{preset.behind()}</g>}
        <path className="aa-body" d={preset.shape} />
        <g transform={`translate(${preset.look.x} ${preset.look.y})`}>
          <g className="aa-gaze">
            {[-6.6, 6.6].map(dx => (
              <g key={dx} transform={`translate(${dx} 0)`}>
                <g className="aa-eye">
                  <rect className="aa-pupil" x="-3.6" y="-8" width="7.2" height="16" rx="3.6" />
                  <path className="aa-happy" d="M-4.4 2 Q0 -5.5 4.4 2" />
                </g>
              </g>
            ))}
            {preset.nose && <ellipse className="aa-nose" cx="0" cy="10.5" rx="2.6" ry="1.9" />}
          </g>
        </g>
      </g>
    </svg>
  );
}
