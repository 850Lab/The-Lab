/**
 * Step `StepMainColumn` top padding with `TopBarMinimal` (fixed, `h-14` / 3.5rem).
 *
 * **ProgramShellFrame (active workflow):** the frame root uses `pt-14` so the program block
 * starts below the app bar. The column only needs a small gap before the task area.
 *
 * **No shell (no `workflowId`):** `ProgramShellFrame` returns children only; the column must
 * clear the top bar by itself (legacy `pt-24` or the upload `calc(3.5rem+…)` pattern).
 */
export function stepMainColumnTopClass(
  inProgramShell: boolean,
  variant: "default" | "upload" | "analysis" = "default",
): string {
  if (inProgramShell) {
    if (variant === "upload") return "pt-2 sm:pt-3";
    if (variant === "analysis") return "pt-1 sm:pt-2";
    return "pt-1 sm:pt-2";
  }
  if (variant === "upload") {
    return "pt-[calc(3.5rem+0.75rem)] sm:pt-[calc(3.5rem+1rem)]";
  }
  return "pt-24 sm:pt-28";
}
