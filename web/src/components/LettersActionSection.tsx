import { motion } from "framer-motion";
import { combinedLettersDownloadText } from "@/lib/mockLetterGroups";

type Props = {
  onSend: () => void;
};

export function LettersActionSection({ onSend }: Props) {
  const handleDownload = () => {
    const text = combinedLettersDownloadText();
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "850-lab-dispute-letters-preview.txt";
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mt-10 space-y-3 sm:mt-11">
      <motion.button
        type="button"
        onClick={onSend}
        className="w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/25 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/45"
        whileHover={{
          scale: 1.015,
          boxShadow: "0 14px 44px -10px rgba(59,130,246,0.42)",
        }}
        whileTap={{ scale: 0.985 }}
        transition={{ type: "spring", stiffness: 420, damping: 28 }}
      >
        We’ll send these for you
      </motion.button>
      <motion.button
        type="button"
        onClick={handleDownload}
        className="w-full rounded-xl border border-white/[0.12] bg-transparent py-3.5 text-[15px] font-medium text-lab-text transition-colors hover:border-white/[0.18] hover:bg-white/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/35"
        whileHover={{ y: -1 }}
        whileTap={{ scale: 0.99 }}
        transition={{ type: "spring", stiffness: 480, damping: 30 }}
      >
        Download letters
      </motion.button>
    </div>
  );
}
