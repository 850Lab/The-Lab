import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { ActivationCard } from "@/components/ActivationCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { setWorkflowStep } from "@/lib/workflow";

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.04 },
  },
};

const headerVariants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

const cardRevealVariants = {
  hidden: { opacity: 0, y: 22 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
  },
};

export function PaymentPage() {
  const navigate = useNavigate();

  const handleActivate = () => {
    setWorkflowStep("letters");
    navigate("/letters", { replace: true });
  };

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[36%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.09] blur-[110px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[40%] z-0 h-[min(48vw,320px)] w-[min(48vw,320px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.04] blur-[90px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-md px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        <motion.div variants={pageVariants} initial="hidden" animate="show">
          <motion.p
            variants={headerVariants}
            className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
          >
            Activate
          </motion.p>
          <motion.h1
            variants={headerVariants}
            className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
          >
            Start your disputes
          </motion.h1>
          <motion.p
            variants={headerVariants}
            className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
          >
            We’ve prepared everything — we’ll handle this for you.
          </motion.p>

          <motion.div variants={cardRevealVariants} className="mt-10 sm:mt-11">
            <ActivationCard onActivate={handleActivate} />
          </motion.div>
        </motion.div>
      </main>
    </div>
  );
}
