// How DONNA sounds. A strip under the header, not a dialog: it shows what the
// backend says she is set to, never what we just asked for, so a value she
// refused visibly snaps back.

export type Sound = { voice: string; speed: number };

const REGIONS: Record<string, string> = { en_US: "American", en_GB: "British" };

// Kokoro names its voices by language and gender: "af_heart" is an American
// female called Heart, "bm_george" a British male called George.
const KOKORO_WHO: Record<string, string> = {
  af: "American female",
  am: "American male",
  bf: "British female",
  bm: "British male",
};

/**
 * A Piper voice id as something worth reading in a menu.
 *
 * The id stays the value -- it is what the backend loads -- so this is purely
 * what you see: "en_GB-jenny_dioco-medium" is fine as a filename and no way
 * to label a list of six.
 *
 * "richer" is Piper's "high" quality. It is not free: measured on this PC a
 * high voice synthesises a sentence in 0.70s against a medium voice's 0.14s,
 * which is about half a second more before she starts talking.
 */
export function voiceLabel(id: string): string {
  if (id.startsWith("kokoro:")) {
    // "kokoro:af_heart" -> "Heart — American female, Kokoro"
    const [group, ...rest] = id.slice("kokoro:".length).split("_");
    const person = rest.join("_") || group;
    const who = KOKORO_WHO[group];
    return `${capitalise(person)} — ${[who, "Kokoro"].filter(Boolean).join(", ")}`;
  }
  const [region, name, quality] = id.split("-");
  if (!name) return id; // not a voice id we recognise; show it as it is
  const where = REGIONS[region];
  const detail = [where, quality === "high" ? "richer" : null].filter(Boolean).join(", ");
  const spoken = capitalise(name.split("_")[0]);
  return detail ? `${spoken} — ${detail}` : spoken;
}

function capitalise(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

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
              {voiceLabel(voice)}
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
