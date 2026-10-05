import { useState, type FormEvent } from "react";

interface Props {
  enabled: boolean;
  busy: boolean;
  onSend: (text: string) => void;
  onCancel: () => void;
}

/** Text input stands in for push-to-talk until the microphone adapter exists. */
export function Composer({ enabled, busy, onSend, onCancel }: Props) {
  const [text, setText] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
  };
  return (
    <form className="composer" onSubmit={submit}>
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={enabled ? "Type to DONNA… (e.g. find my TrialGuard files)" : "Not connected"}
        disabled={!enabled}
        maxLength={2000}
        aria-label="Message"
      />
      <button type="submit" disabled={!enabled || !text.trim()}>
        Send
      </button>
      <button type="button" onClick={onCancel} disabled={!enabled || !busy}>
        Cancel
      </button>
    </form>
  );
}
