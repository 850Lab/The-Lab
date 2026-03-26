import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";

type Tab = "draw" | "type";

export type SignatureCardProps = {
  mode: Tab;
  onModeChange: (mode: Tab) => void;
  typedValue: string;
  onTypedChange: (value: string) => void;
  drawDataUrl: string | null;
  drawComplete: boolean;
  onDrawConfirm: (dataUrl: string) => void;
  onDrawClear: () => void;
  complete: boolean;
};

export function SignatureCard({
  mode,
  onModeChange,
  typedValue,
  onTypedChange,
  drawDataUrl,
  drawComplete,
  onDrawConfirm,
  onDrawClear,
  complete,
}: SignatureCardProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const hasInk = useRef(false);
  const [editingDraw, setEditingDraw] = useState(!drawDataUrl || !drawComplete);
  const last = useRef<{ x: number; y: number } | null>(null);

  const setupCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    ctx.strokeStyle = "rgba(230, 237, 243, 0.92)";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }, []);

  useEffect(() => {
    if (mode !== "draw") return;
    setEditingDraw(!(drawDataUrl && drawComplete));
  }, [mode, drawDataUrl, drawComplete]);

  useEffect(() => {
    if (mode !== "draw" || !editingDraw) return;
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => setupCanvas());
    });
    return () => cancelAnimationFrame(id);
  }, [mode, editingDraw, setupCanvas]);

  const pos = (e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const r = canvas.getBoundingClientRect();
    const clientX = "touches" in e ? e.touches[0]?.clientX : e.clientX;
    const clientY = "touches" in e ? e.touches[0]?.clientY : e.clientY;
    if (clientX === undefined || clientY === undefined) return null;
    return { x: clientX - r.left, y: clientY - r.top };
  };

  const start = (e: React.MouseEvent | React.TouchEvent) => {
    if (!editingDraw) return;
    const p = pos(e);
    if (!p) return;
    drawing.current = true;
    last.current = p;
  };

  const move = (e: React.MouseEvent | React.TouchEvent) => {
    if (!drawing.current || !editingDraw) return;
    const p = pos(e);
    if (!p || !last.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!ctx) return;
    ctx.beginPath();
    ctx.moveTo(last.current.x, last.current.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    hasInk.current = true;
    last.current = p;
  };

  const end = () => {
    drawing.current = false;
    last.current = null;
  };

  const handleConfirmDraw = () => {
    if (!hasInk.current) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    try {
      const url = canvas.toDataURL("image/png");
      onDrawConfirm(url);
      setEditingDraw(false);
    } catch {
      /* ignore */
    }
  };

  const handleClearCanvas = () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    hasInk.current = false;
    setupCanvas();
    onDrawClear();
  };

  const handleRedraw = () => {
    onDrawClear();
    hasInk.current = false;
    setEditingDraw(true);
    requestAnimationFrame(() => setupCanvas());
  };

  return (
    <motion.section
      variants={{
        hidden: { opacity: 0, y: 16 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.44, ease: [0.22, 1, 0.36, 1] },
        },
      }}
      className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-5 shadow-lg shadow-black/15 sm:px-6 sm:py-6"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-[15px] font-semibold text-lab-text sm:text-base">
            Add your signature
          </h3>
          <p className="mt-1.5 text-sm leading-relaxed text-lab-muted">
            We’ll place this on your dispute letters
          </p>
        </div>
        <AnimatePresence mode="wait">
          {complete ? (
            <motion.span
              key="ok"
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
              className="flex h-8 shrink-0 items-center rounded-full bg-emerald-500/12 px-2.5 text-xs font-medium text-emerald-300/95"
            >
              Added
            </motion.span>
          ) : null}
        </AnimatePresence>
      </div>

      <div
        className="mt-5 flex rounded-lg border border-white/[0.08] bg-lab-elevated/50 p-1"
        role="tablist"
        aria-label="Signature method"
      >
        {(["draw", "type"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={mode === tab}
            onClick={() => onModeChange(tab)}
            className={`flex-1 rounded-md py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/35 ${
              mode === tab
                ? "bg-lab-elevated text-lab-text shadow-sm shadow-black/20"
                : "text-lab-muted hover:text-lab-text"
            }`}
          >
            {tab === "draw" ? "Draw" : "Type"}
          </button>
        ))}
      </div>

      <div className="mt-5">
        <AnimatePresence mode="wait">
          {mode === "draw" ? (
            <motion.div
              key="draw"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.28 }}
              className="space-y-4"
            >
              {!editingDraw && drawDataUrl ? (
                <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-lab-bg/90">
                  <div className="flex items-center justify-center bg-lab-bg px-4 py-6">
                    <img
                      src={drawDataUrl}
                      alt="Your signature"
                      className="max-h-28 max-w-full object-contain"
                    />
                  </div>
                  <div className="flex gap-2 border-t border-white/[0.06] px-4 py-3">
                    <button
                      type="button"
                      onClick={handleRedraw}
                      className="rounded-lg border border-white/[0.12] px-3 py-2 text-sm font-medium text-lab-text hover:bg-white/[0.04]"
                    >
                      Redraw
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="rounded-xl border border-dashed border-white/[0.12] bg-lab-bg/80 p-1">
                    <canvas
                      ref={canvasRef}
                      className="h-36 w-full touch-none rounded-lg bg-transparent sm:h-40"
                      onMouseDown={start}
                      onMouseMove={move}
                      onMouseUp={end}
                      onMouseLeave={end}
                      onTouchStart={start}
                      onTouchMove={move}
                      onTouchEnd={end}
                    />
                  </div>
                  <p className="text-center text-xs text-lab-subtle">
                    Sign with your finger or mouse, then confirm below
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={handleConfirmDraw}
                      className="rounded-lg bg-lab-accent/20 px-4 py-2.5 text-sm font-semibold text-lab-accent hover:bg-lab-accent/28"
                    >
                      Use this signature
                    </button>
                    <button
                      type="button"
                      onClick={handleClearCanvas}
                      className="rounded-lg px-4 py-2.5 text-sm text-lab-muted hover:bg-white/[0.04] hover:text-lab-text"
                    >
                      Clear
                    </button>
                  </div>
                </>
              )}
            </motion.div>
          ) : (
            <motion.div
              key="type"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.28 }}
              className="space-y-4"
            >
              <label className="block">
                <span className="sr-only">Type your name</span>
                <input
                  type="text"
                  value={typedValue}
                  onChange={(e) => onTypedChange(e.target.value)}
                  placeholder="Type your full name"
                  autoComplete="name"
                  className="w-full rounded-xl border border-white/[0.1] bg-lab-elevated/80 px-4 py-3.5 text-sm text-lab-text placeholder:text-lab-subtle focus:border-lab-accent/40 focus:outline-none focus:ring-2 focus:ring-lab-accent/25"
                />
              </label>
              <div className="rounded-xl border border-white/[0.06] bg-lab-bg/90 px-4 py-6 text-center">
                <p className="text-xs uppercase tracking-wide text-lab-subtle">
                  Preview
                </p>
                <p
                  className="mt-3 font-[cursive] text-2xl text-lab-text sm:text-[1.65rem]"
                  style={{ fontFamily: "'Segoe Script', 'Brush Script MT', cursive" }}
                >
                  {typedValue.trim() || "Your name"}
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.section>
  );
}
