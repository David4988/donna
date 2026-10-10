// How DONNA sounds. A strip under the header, not a dialog: it shows what the
// backend says she is set to, never what we just asked for, so a value she
// refused visibly snaps back.

export type Sound = { voice: string; speed: number };

export default function Settings({
  sound,
  voices,
  changing,
  onChange,
}: {
  sound: Sound;
  voices: string[];
  changing: boolean;
  onChange: (change: Partial<Sound>) => void;
}) {
  return (
    <section className="settings">
      <label>
        Voice
        <select
          value={sound.voice}
          disabled={changing || voices.length === 0}
          onChange={(event) => onChange({ voice: event.target.value })}
        >
          {voices.length === 0 && <option>none installed</option>}
          {voices.map((voice) => (
            <option key={voice} value={voice}>
              {voice}
            </option>
          ))}
        </select>
      </label>

      <label>
        Speed
        <input
          type="range"
          min="0.5"
          max="2"
          step="0.1"
          value={sound.speed}
          onChange={(event) => onChange({ speed: Number(event.target.value) })}
        />
        <span>{sound.speed.toFixed(1)}×</span>
      </label>

      {/* The backend is synchronous, so this cannot clear until the voice has
          actually loaded -- a correct spinner with no extra protocol. */}
      {changing && <span className="hint">loading…</span>}

      {voices.length === 0 && (
        <span className="hint">
          Add one with <code>python -m piper.download_voices en_GB-alan-medium</code>
        </span>
      )}
    </section>
  );
}
