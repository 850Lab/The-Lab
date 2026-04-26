import { OrionPanel } from "@/components/program/OrionPanel";
import { defaultOrionSurface, useOrionSystem } from "@/providers/OrionSystemContext";

export function OrionProgramRail() {
  const { surface } = useOrionSystem();
  const model = surface ?? defaultOrionSurface();

  return (
    <div className="lg:sticky lg:top-28 lg:self-start">
      <OrionPanel model={model} />
    </div>
  );
}
