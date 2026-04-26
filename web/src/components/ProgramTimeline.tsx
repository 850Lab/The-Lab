import { useLocation } from "react-router-dom";
import { isEscalationPath } from "@/lib/workflowStepRoutes";
import { PROGRAM_TIMELINE, currentTimelineIndex } from "@/lib/programShellConfig";
import type { ProgramState } from "@/lib/programStateTypes";

type Props = {
  programState: ProgramState | null;
};

/**
 * Read-only. Reflects `currentStep` (backend) and route; escalation path highlights follow-up.
 */
export function ProgramTimeline({ programState }: Props) {
  const path = useLocation().pathname;
  const esc = isEscalationPath(path);
  const p = programState;
  const complete = Boolean(p?.isComplete);
  const idx = currentTimelineIndex(p, path);
  return (
    <div
      className="w-full overflow-x-auto border-t border-white/[0.06] pt-3"
      data-program-timeline
      role="list"
      aria-label="Program steps, read-only"
    >
      <ol className="flex w-max min-w-full items-stretch justify-between gap-1.5 pr-1 sm:gap-2 sm:pr-0">
        {PROGRAM_TIMELINE.map((node, i) => {
          if (i < 9) {
            const isDone = complete || esc || (idx < 9 && i < idx);
            const isCurrent = !isDone && !esc && i === idx;
            const isUpcoming = !isDone && !isCurrent;
            return (
              <li
                key={node.id}
                className="flex min-w-0 max-w-[4.2rem] flex-1 flex-col items-center sm:max-w-[4.5rem] md:max-w-[4.8rem]"
                title={node.label}
              >
                <div
                  className={[
                    "mb-0.5 flex h-5 w-5 items-center justify-center rounded-full text-[7px] font-bold",
                    isDone
                      ? "bg-emerald-500/30 text-emerald-100/95 ring-1 ring-emerald-400/40"
                      : isCurrent
                        ? "bg-lab-accent/30 text-lab-text ring-2 ring-lab-accent/50"
                        : isUpcoming
                          ? "bg-zinc-700/30 text-zinc-500/90 ring-1 ring-zinc-600/30"
                          : "bg-zinc-800/40",
                  ].join(" ")}
                  aria-hidden
                >
                  {isDone ? "✓" : isCurrent ? "•" : ""}
                </div>
                <p
                  className={[
                    "text-center text-[6px] font-semibold uppercase leading-tight tracking-tight sm:text-[7px]",
                    isCurrent
                      ? "text-lab-text"
                      : isDone
                        ? "text-emerald-200/75"
                        : "text-lab-subtle/85",
                  ].join(" ")}
                >
                  {node.label}
                </p>
              </li>
            );
          }
          const isCurrent = esc;
          const isUpcoming = !isCurrent;
          return (
            <li
              key={node.id}
              className="flex min-w-0 max-w-[4.2rem] flex-1 flex-col items-center sm:max-w-[4.5rem] md:max-w-[4.8rem]"
              title={node.label}
            >
              <div
                className={[
                  "mb-0.5 flex h-5 w-5 items-center justify-center rounded-full text-[7px] font-bold",
                  isCurrent
                    ? "bg-lab-accent/30 text-lab-text ring-2 ring-lab-accent/50"
                    : isUpcoming
                      ? "bg-zinc-700/30 text-zinc-500/80 ring-1 ring-zinc-600/30"
                      : "bg-zinc-800/40",
                ].join(" ")}
                aria-hidden
              >
                {isCurrent ? "•" : ""}
              </div>
              <p
                className={[
                  "text-center text-[6px] font-semibold uppercase leading-tight tracking-tight sm:text-[7px]",
                  isCurrent ? "text-lab-text" : "text-lab-subtle/85",
                ].join(" ")}
              >
                {node.label}
              </p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
