import type { components } from '@/shared/api/schema';
import styles from './sop.module.css';

type SopStep = components['schemas']['SopStep'];

/** 新增步骤的默认值。契约：单步预计时长约 12 分钟（720 秒）。 */
function newStep(position: number): SopStep {
  return {
    id: crypto.randomUUID(),
    position,
    instruction: '',
    media_ids: [], // 媒体上传属后续里程碑，首版新增步骤不带媒体
    estimated_seconds: 720,
    evidence_required: false,
  };
}

/** 重排 / 删除后按数组顺序重编号 position（1 起，连续）。 */
function renumber(list: SopStep[]): SopStep[] {
  return list.map((s, i) => (s.position === i + 1 ? s : { ...s, position: i + 1 }));
}

/**
 * 可复用的 SOP 步骤编辑组件：增删改 + 上移/下移。
 * 受控组件，不改写传入数组，任何变更都通过 onChange 交回上层。
 */
export function StepList({
  steps,
  onChange,
  disabled = false,
}: {
  steps: SopStep[];
  onChange: (steps: SopStep[]) => void;
  disabled?: boolean;
}) {
  function add() {
    onChange(renumber([...steps, newStep(steps.length + 1)]));
  }
  function update(id: string, patch: Partial<SopStep>) {
    onChange(steps.map(s => (s.id === id ? { ...s, ...patch } : s)));
  }
  function remove(id: string) {
    onChange(renumber(steps.filter(s => s.id !== id)));
  }
  function move(id: string, delta: -1 | 1) {
    const i = steps.findIndex(s => s.id === id);
    const j = i + delta;
    if (i < 0 || j < 0 || j >= steps.length) return;
    const next = [...steps];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(renumber(next));
  }

  return (
    <div className={styles.stepList}>
      {steps.map((step, idx) => (
        <div key={step.id} className={styles.stepCard}>
          <div className={styles.stepHead}>
            <span className={styles.stepNo}>第 {idx + 1} 步</span>
            <div className={styles.stepTools}>
              <button
                type="button"
                disabled={disabled || idx === 0}
                onClick={() => move(step.id, -1)}
              >
                上移
              </button>
              <button
                type="button"
                disabled={disabled || idx === steps.length - 1}
                onClick={() => move(step.id, 1)}
              >
                下移
              </button>
              <button type="button" disabled={disabled} onClick={() => remove(step.id)}>
                删除
              </button>
            </div>
          </div>

          <div className={styles.field}>
            <label htmlFor={`step-instruction-${step.id}`}>步骤说明</label>
            <textarea
              id={`step-instruction-${step.id}`}
              value={step.instruction}
              maxLength={2000}
              rows={2}
              disabled={disabled}
              placeholder="这一步让学员做什么、怎么做"
              onChange={e => update(step.id, { instruction: e.target.value })}
            />
          </div>

          <div className={styles.field}>
            <label htmlFor={`step-seconds-${step.id}`}>预计时长（秒）</label>
            <input
              id={`step-seconds-${step.id}`}
              type="number"
              min={0}
              max={86400}
              step={1}
              value={step.estimated_seconds}
              disabled={disabled}
              onChange={e => update(step.id, { estimated_seconds: Number(e.target.value) })}
            />
          </div>

          <label className={styles.check}>
            <input
              type="checkbox"
              checked={step.evidence_required}
              disabled={disabled}
              onChange={e => update(step.id, { evidence_required: e.target.checked })}
            />
            需提交凭证
          </label>
        </div>
      ))}

      <button type="button" disabled={disabled || steps.length >= 100} onClick={add}>
        添加步骤
      </button>
    </div>
  );
}
