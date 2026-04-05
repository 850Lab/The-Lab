import { motion } from "framer-motion";

type Props = {
  title?: string;
  subtitle?: string;
  /** Tighter vertical padding for dense layouts (e.g. upload step). */
  compact?: boolean;
};

export function UploadProgressState({
  title = "Processing your report…",
  subtitle = "This runs on our servers and may take a moment. Please keep this tab open.",
  compact = false,
}: Props) {
  return (
    <div
      className={`flex flex-col items-center justify-center ${compact ? "py-5 sm:py-6" : "py-10 sm:py-14"}`}
    >
      <motion.div
        className={`relative ${compact ? "h-10 w-10" : "h-12 w-12"}`}
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        <motion.span
          className="absolute inset-0 rounded-full border-2 border-lab-accent/25 border-t-lab-accent"
          animate={{ rotate: 360 }}
          transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }}
        />
        <span className="absolute inset-[6px] rounded-full bg-lab-accent/10" />
      </motion.div>
      <motion.p
        className={`text-center font-medium text-lab-text ${compact ? "mt-4 text-base sm:mt-5 sm:text-lg" : "mt-6 text-lg sm:text-xl"}`}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        {title}
      </motion.p>
      <motion.p
        className={`max-w-xs text-center text-lab-muted ${compact ? "mt-2 text-xs sm:text-sm" : "mt-2 text-sm"}`}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.22, duration: 0.35 }}
      >
        {subtitle}
      </motion.p>
    </div>
  );
}
