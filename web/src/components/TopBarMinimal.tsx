import { motion } from "framer-motion";

export function TopBarMinimal() {
  return (
    <motion.header
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="fixed left-0 right-0 top-0 z-40 border-b border-white/[0.06] bg-lab-surface/75 backdrop-blur-md"
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center px-4 sm:px-6">
        <span className="text-[15px] font-semibold tracking-tight text-lab-text">
          850 Lab
        </span>
      </div>
    </motion.header>
  );
}
