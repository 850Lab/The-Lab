import { motion } from "framer-motion";
import { BureauSendStatusRow } from "@/components/BureauSendStatusRow";

const BUREAUS = ["Equifax", "Experian", "TransUnion"] as const;

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
};

const rowListVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.04 },
  },
};

export function SentState() {
  return (
    <motion.section
      className="mt-2"
      variants={{
        hidden: { opacity: 0 },
        show: {
          opacity: 1,
          transition: { staggerChildren: 0.1, delayChildren: 0.1 },
        },
      }}
      initial="hidden"
      animate="show"
    >
      <motion.h2
        variants={itemVariants}
        className="text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
      >
        Your disputes have been sent
      </motion.h2>
      <motion.p
        variants={itemVariants}
        className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
      >
        We’ll track delivery and keep you updated as each bureau receives your
        letters.
      </motion.p>

      <motion.div
        variants={rowListVariants}
        className="mt-10 flex flex-col gap-2.5 sm:mt-11 sm:gap-3"
      >
        {BUREAUS.map((bureau) => (
          <BureauSendStatusRow key={bureau} bureau={bureau} />
        ))}
      </motion.div>

      <motion.p
        variants={itemVariants}
        className="mx-auto mt-8 max-w-sm text-center text-sm text-lab-subtle sm:mt-9"
      >
        Most bureaus respond within 30 days
      </motion.p>
    </motion.section>
  );
}
