// Turning sound into bytes and back.
//
// These two numbers have to match the backend exactly: stt.SAMPLE_RATE and
// tts.SAMPLE_RATE. If they drift she sounds like a chipmunk, or Whisper hears
// one, and nothing else tells you why.
export const MIC_RATE = 16000; // what we send: PCM16 mono, what Whisper wants

// What she sends back, until the backend says otherwise. It is no longer a
// fact: Piper's medium voices are 22050, Kokoro is 24000 and Piper's low
// voices are 16000, so the real rate arrives with the `settings` message and
// goes to Speaker.speaksAt(). This is only the guess used before it does.
export const VOICE_RATE = 22050;

// One utterance is one WebSocket frame, and the backend drops anything longer.
// Keep this below voice.MAX_UTTERANCE_BYTES.
// 19, not 20: a worklet frame lands every 8ms, so a cap of 20 overshoots to
// 640,256 bytes and the backend -- which drops anything over 640,000 -- threw
// the whole utterance away. Keep this below voice.MAX_UTTERANCE_BYTES.
export const MAX_UTTERANCE_SECONDS = 19;

/**
 * Resample to MIC_RATE, because the browser is allowed to ignore us.
 *
 * `new AudioContext({ sampleRate })` is a REQUEST. Hardware that won't do
 * 16kHz hands back its own rate -- commonly 48000 -- and nothing throws. The
 * gate still works, because it is given the real rate and only measures
 * loudness and time. What breaks is everything downstream: the PCM would go
 * out at 48kHz while Python reads it as 16kHz, so Whisper hears a slur at a
 * third speed and openWakeWord, which accepts no other rate, never fires
 * once. She would look dead with nothing in the log to say why.
 *
 * Linear interpolation is enough here. The input is a 16kHz-bandwidth voice
 * signal being decimated, and the alternative -- a windowed-sinc filter --
 * is a lot of arithmetic to improve audio that then gets handed to a speech
 * recogniser trained on far worse.
 */
export function toRate(samples: Float32Array, from: number, to: number): Float32Array {
  if (from === to || samples.length === 0) return samples;
  const out = new Float32Array(Math.max(1, Math.round((samples.length * to) / from)));
  const step = from / to;
  for (let i = 0; i < out.length; i++) {
    const at = i * step;
    const below = Math.floor(at);
    const above = Math.min(below + 1, samples.length - 1);
    out[i] = samples[below] + (samples[above] - samples[below]) * (at - below);
  }
  return out;
}

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
  private rate = VOICE_RATE;

  /**
   * What rate her audio is in, as the backend reports it.
   *
   * Changes when you pick a different voice, so it has to be told rather
   * than assumed: playing 24000 Hz audio as 22050 makes her 9% too slow and
   * too low, which sounds like a worse voice rather than like a bug.
   */
  speaksAt(rate: number): void {
    if (rate >= 8000 && rate <= 96000) this.rate = rate;
  }

  /** Must be called from a click: an AudioContext starts suspended. */
  async start(): Promise<void> {
    // Deliberately not asking for a sample rate. Each buffer declares its
    // own and the browser resamples to the hardware better than we can, and
    // a forced rate was both a request the browser may ignore and a claim
    // that stopped being true once voices disagreed about it.
    this.context ??= new AudioContext();
    if (this.context.state === "suspended") await this.context.resume();
  }

  get busy(): boolean {
    return this.context !== null && this.endsAt > this.context.currentTime;
  }

  play(pcm: ArrayBuffer): void {
    const context = this.context;
    if (!context) return; // nobody pressed Start voice; nothing to play through

    const samples = new Int16Array(pcm);
    if (samples.length === 0) return; // createBuffer throws on a zero length
    const buffer = context.createBuffer(1, samples.length, this.rate);
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

// How much of the room to keep from BEFORE you started talking.
//
// This is what makes a bare "Jarvis" wake her. openWakeWord classifies with a
// receptive field of about two seconds, so a one-word utterance arriving with
// nothing in front of it is being judged on almost no context. Measured on a
// deliberately clipped "Jarvis": 0.09-0.27 whatever zero padding it was given
// -- never reaching the 0.5 threshold -- but 0.597 when the padding was quiet
// room noise instead of digital silence. Real audio is what the model was
// trained on; zeros are out-of-distribution for it.
//
// "Hey Jarvis, open notepad" never needed this: it brings two seconds of its
// own context and scores 0.999. Only the bare summons lives near the edge,
// which is exactly the case that felt broken.
//
// It helps Whisper too: FRAMES_TO_START alone used to leave about 24ms of
// lead-in, so the first phoneme could be clipped.
const PREROLL_MS = 500;

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

  // The room just before you spoke, oldest first. Kept while idle, handed
  // over with the utterance, and never longer than PREROLL_MS.
  private preroll: Float32Array[] = [];
  private prerollSamples = 0;

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
    if (context.sampleRate !== MIC_RATE) {
      // Not fatal -- toRate() fixes the audio on the way out -- but it should
      // be on the record, because it changes what the gate is measuring and
      // it is the first thing to suspect if waking goes strange.
      console.warn(
        `Microphone is running at ${context.sampleRate}Hz, not the ${MIC_RATE}Hz asked for. ` +
          `Resampling every utterance before sending it.`,
      );
    }
    const tap = new AudioWorkletNode(context, "tap");
    tap.port.onmessage = (event) => this.hear(event.data as Float32Array, context.sampleRate);
    context.createMediaStreamSource(this.stream).connect(tap);
    this.context = context;
  }

  /** What the microphone is really running at, whatever we asked for. */
  get rate(): number {
    return this.context?.sampleRate ?? MIC_RATE;
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
    this.preroll = [];
    this.prerollSamples = 0;
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
      // Hold on to the room while it is quiet. Dropping these frames is what
      // left the wake word with no context on a one-word summons.
      this.preroll.push(frame);
      this.prerollSamples += frame.length;
      const keep = (PREROLL_MS / 1000) * rate;
      while (this.prerollSamples > keep && this.preroll.length > 1) {
        this.prerollSamples -= this.preroll.shift()!.length;
      }

      this.loudFrames = loud ? this.loudFrames + 1 : 0;
      if (this.loudFrames < FRAMES_TO_START) return;

      // Start from the pre-roll, which already holds the frames that
      // triggered this -- including the first two, which used to be thrown
      // away despite the old comment claiming otherwise.
      this.speaking = true;
      this.collecting = this.preroll;
      this.samples = this.prerollSamples;
      this.preroll = [];
      this.prerollSamples = 0;
      return; // this frame is already in there, via the pre-roll
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
      this.onPartial(this.joined(rate));
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

  /** Everything heard so far, at MIC_RATE whatever the microphone runs at. */
  private joined(rate: number): Float32Array {
    return toRate(join(this.collecting, this.samples), rate, MIC_RATE);
  }

  private finish(rate: number) {
    const { collecting, samples } = this;
    this.reset();
    this.quietSince = 0;
    if (samples < 0.3 * rate) return; // a cough, a click, a door

    this.onUtterance(toRate(join(collecting, samples), rate, MIC_RATE));
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
