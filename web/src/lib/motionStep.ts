/**
 * Shared Framer Motion presets for STEP / customer workflow routes.
 * Short duration, small travel, light stagger — polished but not theatrical.
 */
export const easeStep: [number, number, number, number] = [0.22, 1, 0.36, 1];

export const durationStep = 0.32;

/** Main column entrance (matches StepMainColumn + CSS micro-transitions ~220ms) */
export const transitionStepUi = { duration: 0.22, ease: easeStep } as const;

export const stepChildVariants = {
  hidden: { opacity: 0, y: 6 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: durationStep, ease: easeStep },
  },
};

/** List rows / cards — slightly more travel, still subtle */
export const stepCardChildVariants = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.34, ease: easeStep },
  },
};

export const stepPageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.04, delayChildren: 0.02 },
  },
};

export const stepNestedStaggerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.03 },
  },
};

export const stepListGroupVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.02 },
  },
};

/** Proof page stacked sections */
export const stepStackVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.07, delayChildren: 0.04 },
  },
};

/** Error / recovery panels — fade + tiny nudge */
export const stepSoftRevealVariants = {
  hidden: { opacity: 0, y: 4 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.28, ease: easeStep },
  },
};
