export function ErrorBanner({ message, onDismiss }: { message: string | null; onDismiss: () => void }) {
  if (!message) return null;
  return (
    <div className="error-banner" role="alert">
      <span>{message}</span>
      <button onClick={onDismiss} aria-label="Dismiss">
        ×
      </button>
    </div>
  );
}
