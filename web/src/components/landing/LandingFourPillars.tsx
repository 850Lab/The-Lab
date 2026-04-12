import { motion } from "framer-motion";

const pillars = [
  {
    title: "Find what's off",
    copy: "We surface what doesn't line up across your report.",
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.25}>
        <circle cx="12" cy="12" r="3" className="text-zinc-400" />
        <path
          strokeLinecap="round"
          d="M12 5v2M12 17v2M5 12h2M17 12h2M7.05 7.05l1.42 1.42M15.54 15.54l1.41 1.41M7.05 16.95l1.42-1.41M15.54 8.46l1.41-1.41"
          className="text-white/50"
        />
      </svg>
    ),
  },
  {
    title: "Understand what changed",
    copy: "Different situations require different moves.",
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.25}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h8M8 12h5M8 17h8" className="text-white/45" />
        <path strokeLinecap="round" d="M16 12l2 2-2 2" className="text-zinc-400" />
      </svg>
    ),
  },
  {
    title: "See the strategy",
    copy: "The system adjusts based on what it finds.",
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.25}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M6 18L18 6M10 6h8v8"
          className="text-zinc-400"
        />
        <circle cx="6" cy="18" r="1.5" fill="currentColor" className="text-white/60" />
      </svg>
    ),
  },
  {
    title: "Get the output",
    copy: "Generate dispute letters you can actually use.",
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.25}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9 12h6m-6 4h4M8 6h8a2 2 0 012 2v8l-4-2-4 2-4-2-4 2V8a2 2 0 012-2z"
          className="text-zinc-400"
        />
      </svg>
    ),
  },
] as const;

const cardMotion = {
  hidden: { opacity: 0, y: 20 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.07, duration: 0.5, ease: [0.22, 1, 0.36, 1] },
  }),
};

export function LandingFourPillars() {
  return (
    <section className="relative z-10 mx-auto mt-16 max-w-5xl px-4 sm:mt-20 sm:px-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:gap-5">
        {pillars.map((p, i) => (
          <motion.article
            key={p.title}
            custom={i}
            variants={cardMotion}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-40px" }}
            whileHover={{ y: -3, transition: { duration: 0.2 } }}
            className="group relative overflow-hidden rounded-xl border border-white/20 bg-white/[0.07] p-5 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.12)] backdrop-blur-sm transition-[border-color,box-shadow] duration-300 hover:border-white/30 hover:bg-white/[0.1] hover:shadow-[0_24px_56px_-28px_rgba(0,0,0,0.55)]"
          >
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg border border-white/20 bg-white/[0.08] text-white transition-colors group-hover:border-white/35">
              {p.icon}
            </div>
            <h3 className="font-heading text-base font-semibold tracking-tight text-white">{p.title}</h3>
            <p className="mt-2 text-sm font-medium leading-snug text-neutral-200">{p.copy}</p>
          </motion.article>
        ))}
      </div>
    </section>
  );
}
