import { motion } from "framer-motion";
import { useState } from "react";
import { BureauTrackingRow } from "@/components/BureauTrackingRow";
import { ExpectationsCard } from "@/components/ExpectationsCard";
import { ProgressTimelineCard } from "@/components/ProgressTimelineCard";
import { ResponseUploadCard } from "@/components/ResponseUploadCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { TrackingDetailsModal } from "@/components/TrackingDetailsModal";
import { BUREAU_ROWS, type BureauTrackingInfo } from "@/lib/mockTrackingData";

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.05 },
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

const stackVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.06 },
  },
};

const subheadingVariants = {
  hidden: { opacity: 0, y: 10 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.38, ease: [0.22, 1, 0.36, 1] },
  },
};

export function TrackingPage() {
  const [modalBureau, setModalBureau] = useState<BureauTrackingInfo | null>(
    null,
  );

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[34%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.09] blur-[110px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[42%] z-0 h-[min(48vw,300px)] w-[min(48vw,300px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.04] blur-[90px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-md px-4 pb-28 pt-24 sm:px-6 sm:pb-32 sm:pt-28">
        <motion.div
          variants={pageVariants}
          initial="hidden"
          animate="show"
          className="pb-4"
        >
          <motion.p
            variants={headerVariants}
            className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
          >
            Tracking
          </motion.p>
          <motion.h1
            variants={headerVariants}
            className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
          >
            Your disputes are in progress
          </motion.h1>
          <motion.p
            variants={headerVariants}
            className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
          >
            The credit bureaus are reviewing your requests. We’ll keep you
            updated as delivery and review progress.
          </motion.p>

          <motion.div
            variants={stackVariants}
            initial="hidden"
            animate="show"
            className="mt-10 flex flex-col gap-5 sm:mt-11 sm:gap-6"
          >
            <ProgressTimelineCard />

            <motion.h2
              variants={subheadingVariants}
              className="text-sm font-semibold text-lab-text"
            >
              Your letters
            </motion.h2>

            {BUREAU_ROWS.map((row) => (
              <BureauTrackingRow
                key={row.id}
                bureau={row.name}
                status={row.mainStatus}
                onViewTracking={() => setModalBureau(row)}
              />
            ))}

            <ExpectationsCard />
            <ResponseUploadCard />
          </motion.div>
        </motion.div>
      </main>

      <TrackingDetailsModal
        open={modalBureau !== null}
        onClose={() => setModalBureau(null)}
        bureau={modalBureau}
      />
    </div>
  );
}
