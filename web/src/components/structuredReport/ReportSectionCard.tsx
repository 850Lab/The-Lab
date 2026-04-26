import type { ReactNode } from "react";

type Props = {
  title: string;
  description?: string;
  children: ReactNode;
};

/**
 * Calm, single-purpose section for the customer structured report (not MC).
 */
export function ReportSectionCard({ title, description, children }: Props) {
  return (
    <section className="rounded-2xl border border-white/[0.08] bg-lab-surface/35 p-4 sm:p-5">
      <h2 className="text-base font-semibold tracking-tight text-lab-text">{title}</h2>
      {description ? (
        <p className="mt-1 text-sm leading-relaxed text-lab-subtle">{description}</p>
      ) : null}
      <div className="mt-4 space-y-3 text-sm text-lab-muted">{children}</div>
    </section>
  );
}
