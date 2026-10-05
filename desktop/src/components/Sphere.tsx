import type { AssistantState } from "../protocol/generated";

/** Placeholder for the shader-driven golden sphere. Reacts to state only. */
export function Sphere({ state }: { state: AssistantState }) {
  return (
    <div className="sphere-stage" aria-label={`DONNA is ${state.toLowerCase()}`}>
      <div className={`sphere sphere-${state}`} />
    </div>
  );
}
