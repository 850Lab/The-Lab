import { motion } from "framer-motion";

/**
 * Dark stage with a brighter “spotlight” so foreground UI reads as illuminated.
 */
export function LandingAmbientLayer() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_100%_70%_at_50%_-15%,rgba(255,255,255,0.06),transparent_58%)]" />
      <motion.div
        className="absolute -left-[20%] top-[8%] h-[min(100vw,680px)] w-[min(100vw,680px)] rounded-full bg-gradient-to-br from-white/[0.08] via-white/[0.03] to-transparent blur-[110px]"
        animate={{ opacity: [0.55, 0.9, 0.55], scale: [1, 1.04, 1] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute -right-[12%] bottom-[0%] h-[min(85vw,520px)] w-[min(85vw,520px)] rounded-full bg-gradient-to-tl from-white/[0.12] via-white/[0.04] to-transparent blur-[95px]"
        animate={{ opacity: [0.45, 0.75, 0.45] }}
        transition={{ duration: 11, repeat: Infinity, ease: "easeInOut", delay: 1 }}
      />
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
        }}
      />
    </div>
  );
}
