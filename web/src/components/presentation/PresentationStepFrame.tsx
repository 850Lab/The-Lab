import { useState, type ReactNode } from "react";

type Props = {
  /** Top region: eyebrow is usually ProgramShell; headline + subtext go here. */
  top: ReactNode;
  /** One primary content block: card, list, or interaction. */
  center: ReactNode;
  /** Primary action bar (one clear CTA). */
  bottom?: ReactNode;
  className?: string;
  /** Min height helps steps feel like a slide; allow scroll when content is expanded. */
  variant?: "tight" | "comfortable";
};

/**
 * Phase 6.5: shared “slide” structure — one idea, one primary block, one action.
 * Secondary copy should live in children of `center` (details / expand) or `/report`.
 */
export function PresentationStepFrame({
  top,
  center,
  bottom,
  className = "",
  variant = "comfortable",
}: Props) {
  const minH =
    variant === "tight"
      ? "min-h-[min(100vh,880px)]"
      : "min-h-[min(100dvh,920px)]";
  return (
    <div
      className={`flex w-full max-w-2xl flex-col ${minH} ${className}`.trim()}
    >
      <div className="shrink-0 pt-0">{top}</div>
      <div className="mt-4 flex min-h-0 flex-1 flex-col justify-center sm:mt-5">
        {center}
      </div>
      {bottom ? <div className="mt-8 shrink-0 pb-1 sm:mt-10">{bottom}</div> : null}
    </div>
  );
}

type DetailsProps = {
  label: string;
  children: ReactNode;
  className?: string;
  defaultOpen?: boolean;
};

/** Secondary detail pattern — keep primary view quiet. */
export function PresentationDetails({
  label,
  children,
  className = "",
  defaultOpen = false,
}: DetailsProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details
      className={`details-calm group rounded-xl border border-white/[0.08] bg-lab-surface/50 ${className}`}
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary className="cursor-pointer list-none px-4 py-3 text-center text-sm font-medium text-lab-muted marker:content-none [&::-webkit-details-marker]:hidden">
        <span className="underline decoration-white/12 underline-offset-2 group-open:text-lab-accent">
          {label}
        </span>
      </summary>
      <div className="border-t border-white/[0.06] px-4 py-3 text-left text-sm leading-relaxed text-lab-muted sm:px-5 sm:py-4">
        {children}
      </div>
    </details>
  );
}
