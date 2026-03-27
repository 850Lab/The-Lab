import { motion } from "framer-motion";
import { useEffect, useState } from "react";

const STEPS = ["Upload", "Analyze", "Prepare", "Send"] as const;

export function ProcessStripAnimated() {
  const [pulseIndex, setPulseIndex] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setPulseIndex((i) => (i + 1) % STEPS.length);
    }, 1800);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="mx-auto w-full max-w-md sm:max-w-lg">
      <div className="relative px-1">
        <div
          className="absolute left-[14%] right-[14%] top-[11px] h-px overflow-hidden rounded-full bg-white/[0.08] sm:top-[13px]"
          aria-hidden
        >
          <motion.div
            className="h-full w-2/5 bg-gradient-to-r from-transparent via-lab-accent/55 to-transparent"
            animate={{ x: ["-120%", "320%"] }}
            transition={{
              duration: 5.5,
              repeat: Infinity,
              ease: "linear",
            }}
          />
        </div>
        <ul className="relative flex justify-between gap-1">
          {STEPS.map((label, i) => {
            const active = i === pulseIndex;
            return (
              <li key={label} className="flex flex-1 flex-col items-center">
                <motion.div
                  className="relative flex h-6 w-6 items-center justify-center sm:h-7 sm:w-7"
                  animate={{
                    scale: active ? 1.08 : 1,
                  }}
                  transition={{
                    type: "spring",
                    stiffness: 380,
                    damping: 22,
                  }}
                >
                  <span
                    className={`absolute inset-0 rounded-full transition-colors duration-500 ${
                      active
                        ? "bg-lab-accent/25 ring-1 ring-lab-accent/50"
                        : "bg-lab-elevated ring-1 ring-white/[0.08]"
                    }`}
                  />
                  <motion.span
                    className="relative z-[1] h-1.5 w-1.5 rounded-full bg-lab-accent"
                    animate={{
                      opacity: active ? 1 : 0.35,
                      scale: active ? 1 : 0.85,
                    }}
                    transition={{ duration: 0.35 }}
                  />
                </motion.div>
                <motion.span
                  className={`mt-2 text-center text-[11px] font-medium uppercase tracking-[0.14em] sm:text-xs ${
                    active ? "text-lab-text" : "text-lab-subtle"
                  }`}
                  animate={{ opacity: active ? 1 : 0.65 }}
                >
                  {label}
                </motion.span>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
