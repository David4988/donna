// Turning sound into bytes and back.
//
// These two numbers have to match the backend exactly: stt.SAMPLE_RATE and
// tts.SAMPLE_RATE. If they drift she sounds like a chipmunk, or Whisper hears
// one, and nothing else tells you why.
export const MIC_RATE = 16000; // what we send: PCM16 mono, what Whisper wants
export const VOICE_RATE = 22050; // what she sends back: PCM16 mono, Piper's rate

// One utterance is one WebSocket frame, and the backend drops anything longer.
// Keep this below voice.MAX_UTTERANCE_BYTES.
// 19, not 20: a worklet frame lands every 8ms, so a cap of 20 overshoots to
// 640,256 bytes and the backend -- which drops anything over 640,000 -- threw
// the whole utterance away. Keep this below voice.MAX_UTTERANCE_BYTES.
export const MAX_UTTERANCE_SECONDS = 19;

/**
 * Float samples (-1..1) to little-endian PCM16, which is what the wire and
 * Whisper both expect.
 *
 * This is the only piece of the audio path whose correctness is arguable
 * rather than audible, which is why it is a plain exported function: a wrong
 * scale factor or the wrong endianness produces static, and static sounds
 * like a hardware fault rather than a bug.
 */
export function toPcm16(samples: Float32Array): ArrayBuffer {
  const out = new DataView(new ArrayBuffer(samples.length * 2));
  for (let i = 0; i < samples.length; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    out.setInt16(i * 2, Math.round(clamped * 32767), true); // true = little-endian
  }
  return out.buffer;
}

/**
 * Plays her reply, one sentence at a time, without gaps.
 *
 * Each sentence arrives as its own frame while the model is still writing the
 * rest, so playback is a schedule rather than a queue: every chunk starts
 * when the previous one ends, or now if nothing is playing. The backend keeps
 * the same running total to know when she has finished talking.
 */
export class Speaker {
  private context: AudioContext | null = null;
  private endsAt = 0;

  /** Must be called from a click: an AudioContext starts suspended. */
  async start(): Promise<void> {
    this.context ??= new AudioContext({ sampleRate: VOICE_RATE });
    if (this.context.state === "suspended") await this.context.resume();
  }

  get busy(): boolean {
    return this.context !== null && this.endsAt > this.context.currentTime;
  }

  play(pcm: ArrayBuffer): void {
    const context = this.context;
    if (!context) return; // nobody pressed Start voice; nothing to play through

    const samples = new Int16Array(pcm);
    const buffer = context.createBuffer(1, samples.length, VOICE_RATE);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 32768;

    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    const startAt = Math.max(context.currentTime, this.endsAt);
    source.start(startAt);
    this.endsAt = startAt + buffer.duration;
  }

  /** Drop anything still scheduled. Used when the connection goes away. */
  stop(): void {
    this.endsAt = 0;
  }
}

// --------------------------------------------------------------- the microphone

// A tiny AudioWorklet that just forwards raw samples to us. It is a string
// rather than a file because a worklet has to be fetched from a URL, and
// making that URL survive both the dev server and the packaged app is more
// trouble than a Blob.
const TAP_WORKLET = `
class Tap extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) this.port.postMessage(channel.slice(0));
    return true;
  }
}
registerProcessor("tap", Tap);
`;

const SILENCE_TO_END_MS = 700; // quiet for this long means you've finished
const PARTIAL_EVERY_MS = 600; // how often to show what you've said so far
const PARTIAL_AFTER_MS = 1000; // ...but not until there's something worth reading
const FRAMES_TO_START = 3; // this many loud frames in a row means you've started
const FLOOR = 0.012; // below this is never speech, however quiet the room
const OVER_FLOOR = 2.5; // speech is this much louder than the room

/**
 * Listens, and hands over each utterance when you stop talking.
 *
 * This is an energy gate: loud enough for long enough is speech, and a pause
 * ends it. A neural detector (Silero) is more precise about what counts as a
 * voice, but needs an ONNX model and onnxruntime's WebAssembly fetched at
 * runtime, which the dev server and the bundler disagree about. The wake word
 * is what actually decides whether DONNA answers, so a rough gate costs CPU
 * -- Whisper transcribes the occasional door slam -- rather than correctness.
 * Swapping Silero back in means replacing this class and nothing else.
 */
export class Mic {
  private context: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private collecting: Float32Array[] = [];
  private samples = 0;
  private loudFrames = 0;
  private quietSince = 0;
  private speaking = false;
  private noiseFloor = FLOOR;

  private partialAt = 0;

  constructor(
    private readonly onUtterance: (audio: Float32Array) => void,
    private readonly onPartial?: (audio: Float32Array) => void,
  ) {}

  get running(): boolean {
    return this.context !== null;
  }

  /** Must be called from a click: browsers only grant a microphone on a gesture. */
  async start(): Promise<void> {
    if (this.context) return;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: MIC_RATE,
        echoCancellation: true, // so she doesn't hear herself through the speakers
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    const context = new AudioContext({ sampleRate: MIC_RATE });
    await context.audioWorklet.addModule(
      URL.createObjectURL(new Blob([TAP_WORKLET], { type: "application/javascript" })),
    );
    const tap = new AudioWorkletNode(context, "tap");
    tap.port.onmessage = (event) => this.hear(event.data as Float32Array, context.sampleRate);
    context.createMediaStreamSource(this.stream).connect(tap);
    this.context = context;
  }

  stop(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    void this.context?.close();
    this.context = null;
    this.stream = null;
    this.reset();
  }

  private reset() {
    this.collecting = [];
    this.samples = 0;
    this.loudFrames = 0;
    this.speaking = false;
    this.partialAt = 0;
  }

  private hear(frame: Float32Array, rate: number) {
    let sum = 0;
    for (let i = 0; i < frame.length; i++) sum += frame[i] * frame[i];
    const loudness = Math.sqrt(sum / frame.length);

    if (!this.speaking) {
      // Drift the noise floor towards whatever the room is doing when quiet.
      this.noiseFloor = Math.max(FLOOR, this.noiseFloor * 0.995 + loudness * 0.005);
    }
    const loud = loudness > this.noiseFloor * OVER_FLOOR;

    if (!this.speaking) {
      this.loudFrames = loud ? this.loudFrames + 1 : 0;
      if (this.loudFrames < FRAMES_TO_START) return;
      this.speaking = true; // keep the frames that started it, so no clipped word
    }

    this.collecting.push(frame);
    this.samples += frame.length;

    // Show what you've said so far, every so often, while you keep talking.
    const spokenMs = (this.samples / rate) * 1000;
    if (
      this.onPartial &&
      spokenMs > PARTIAL_AFTER_MS &&
      spokenMs - this.partialAt > PARTIAL_EVERY_MS
    ) {
      this.partialAt = spokenMs;
      this.onPartial(this.joined());
    }

    if (loud) {
      this.quietSince = 0;
    } else {
      const now = (this.samples / rate) * 1000;
      if (!this.quietSince) this.quietSince = now;
      else if (now - this.quietSince > SILENCE_TO_END_MS) return this.finish(rate);
    }

    if (this.samples > MAX_UTTERANCE_SECONDS * rate) this.finish(rate);
  }

  /** Everything heard so far, as one run of samples. */
  private joined(): Float32Array {
    return join(this.collecting, this.samples);
  }

  private finish(rate: number) {
    const { collecting, samples } = this;
    this.reset();
    this.quietSince = 0;
    if (samples < 0.3 * rate) return; // a cough, a click, a door

    this.onUtterance(join(collecting, samples));
  }
}

function join(frames: Float32Array[], total: number): Float32Array {
  const audio = new Float32Array(total);
  let at = 0;
  for (const frame of frames) {
    audio.set(frame, at);
    at += frame.length;
  }
  return audio;
}
