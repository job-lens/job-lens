export function ErrorPanel({ message, retry }: { message: string; retry?: () => void }) {
  return <section role="alert"><p>{message}</p>{retry && <button type="button" onClick={retry}>重试</button>}</section>;
}
export function LoadingState() { return <p role="status">正在读取…</p>; }
export function ModulePage({ title, children }: { title: string; children?: React.ReactNode }) {
  return <section><h1>{title}</h1>{children ?? <p>此模块的业务界面尚未接入。</p>}</section>;
}
