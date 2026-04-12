import type { ReactNode } from "react";

/**
 * Continuity strip — same voice from demo through completion (upload → responses).
 * Strong opening clause + children for scanability.
 */
export function ProgramFlowBridge({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`surface-where-fits text-center text-sm leading-relaxed text-lab-muted transition-[border-color,background-color,box-shadow,color] duration-200 ease-out hover:border-white/[0.12] ${className}`}
    >
      {children}
    </div>
  );
}
