import { motion } from "framer-motion";

type Props = {
  title: string;
  lines: string[];
  variants?: {
    hidden: { opacity: number; y: number };
    show: {
      opacity: number;
      y: number;
      transition: { duration: number; ease: number[] };
    };
  };
};

const defaultVariants = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

export function StrategySectionCard({ title, lines, variants = defaultVariants }: Props) {
  return (
    <motion.section
      variants={variants}
      className="rounded-xl border border-white/[0.07] bg-lab-surface px-5 py-5 sm:px-6 sm:py-6"
    >
      <h2 className="text-base font-semibold text-lab-text sm:text-lg">{title}</h2>
      <ul className="mt-4 space-y-3">
        {lines.map((line) => (
          <li key={line} className="flex gap-3 text-sm leading-relaxed text-lab-muted sm:text-[15px]">
            <span
              className="mt-2 h-1 w-1 shrink-0 rounded-full bg-lab-accent/60"
              aria-hidden
            />
            <span>{line}</span>
          </li>
        ))}
      </ul>
    </motion.section>
  );
}
