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
      className={`rounded-xl border border-white/[0.1] bg-lab-surface/55 px-4 py-3.5 text-center text-sm leading-relaxed text-lab-muted sm:px-5 ${className}`}
    >
      {children}
    </div>
  );
}
