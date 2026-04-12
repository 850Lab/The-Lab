/**
 * Shared decorative background for customer STEP routes — one lighting system across the flow.
 * Parent must be `relative` (and typically `min-h-full` or `min-h-[100dvh]`).
 */
export function StepPageAmbientBackground() {
  return (
    <>
      <div
        className="pointer-events-none absolute left-1/2 top-[38%] z-0 h-[min(68vw,440px)] w-[min(68vw,440px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/[0.04] blur-[88px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[42%] z-0 h-[min(44vw,300px)] w-[min(44vw,300px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/[0.025] blur-[88px]"
        aria-hidden
      />
    </>
  );
}
