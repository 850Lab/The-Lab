type Props = {
  /** Plain-language themes from the user’s review */
  themesText: string;
};

export function StrategySummaryCard({ themesText }: Props) {
  return (
    <div className="rounded-xl border border-lab-accent/20 bg-lab-surface/80 px-5 py-5 sm:px-6 sm:py-5">
      <p className="text-[15px] leading-relaxed text-lab-text sm:text-base">
        Based on your{" "}
        <span className="font-medium text-lab-text">{themesText}</span>, this plan is designed to
        help you move quickly and stay organized.
      </p>
    </div>
  );
}
