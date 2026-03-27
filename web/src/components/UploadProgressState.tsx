import { motion } from "framer-motion";

type Props = {
  title?: string;
  subtitle?: string;
};

export function UploadProgressState({
  title = "Processing your report…",
  subtitle = "This runs on our servers and may take a moment. Please keep this tab open.",
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-10 sm:py-14">
      <motion.div
        className="relative h-12 w-12"
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
        className="mt-6 text-center text-lg font-medium text-lab-text sm:text-xl"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        {title}
      </motion.p>
      <motion.p
        className="mt-2 max-w-xs text-center text-sm text-lab-muted"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.22, duration: 0.35 }}
      >
        {subtitle}
      </motion.p>
    </div>
  );
}
