export function BrandMark({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <img
      src={`${import.meta.env.BASE_URL}brand-mark.svg`}
      width={size}
      height={size}
      className={className}
      alt=""
      aria-hidden="true"
      draggable={false}
    />
  );
}
