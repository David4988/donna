import type { UiState } from "../state/reducer";

export function StatusBar({ state }: { state: UiState }) {
  return (
    <header className="status-bar">
      <span className="brand">D.O.N.N.A.</span>
      <span className={`pill conn-${state.connection}`} data-testid="connection">
        {state.connection}
      </span>
      <span className={`pill state-${state.assistantState}`} data-testid="assistant-state">
        {state.assistantState}
      </span>
    </header>
  );
}
