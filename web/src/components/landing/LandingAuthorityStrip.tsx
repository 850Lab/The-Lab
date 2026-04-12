import { motion } from "framer-motion";

const lines = [
  "Grounded in federal consumer law",
  "Clear process — not guesswork",
  "You can follow how we got there",
] as const;

export function LandingAuthorityStrip() {
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-20px" }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="relative z-10 mx-auto mt-16 max-w-4xl border-y-2 border-white/15 px-4 py-8 sm:mt-20 sm:px-6"
    >
      <ul className="flex flex-col gap-5 text-center sm:flex-row sm:justify-between sm:gap-6 sm:text-left">
        {lines.map((t) => (
          <li
            key={t}
            className="flex-1 text-sm font-semibold tracking-tight text-white before:mx-auto before:mb-2 before:block before:h-0.5 before:w-10 before:rounded-full before:bg-gradient-to-r before:from-transparent before:via-white/35 before:to-transparent sm:before:mx-0"
          >
            {t}
          </li>
        ))}
      </ul>
    </motion.section>
  );
}
