import { TopBarMinimal } from "@/components/TopBarMinimal";

type Props = { title: string; description?: string };

export function WorkflowStepPlaceholder({ title, description }: Props) {
  return (
    <div className="min-h-full bg-lab-bg">
      <TopBarMinimal />
      <main className="mx-auto max-w-2xl px-4 pb-16 pt-24 sm:px-6 sm:pt-28">
        <h1 className="text-2xl font-semibold text-lab-text">{title}</h1>
        <p className="mt-3 text-lab-muted">
          {description ??
            "This step resumes your saved workflow. Replace with your product UI."}
        </p>
      </main>
    </div>
  );
}
