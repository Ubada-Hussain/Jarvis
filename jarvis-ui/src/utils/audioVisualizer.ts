export class AudioVisualizer {
  private static instance: AudioVisualizer;
  
  private audioCtx: AudioContext | null = null;
  
  // Mic
  private micAnalyser: AnalyserNode | null = null;
  private micDataArray: Uint8Array | null = null;
  private micStream: MediaStream | null = null;
  private micSource: MediaStreamAudioSourceNode | null = null;

  // TTS
  private ttsAnalyser: AnalyserNode | null = null;
  private ttsDataArray: Uint8Array | null = null;

  private constructor() {}

  public static getInstance(): AudioVisualizer {
    if (!AudioVisualizer.instance) {
      AudioVisualizer.instance = new AudioVisualizer();
    }
    return AudioVisualizer.instance;
  }

  private initContext() {
    if (!this.audioCtx) {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioContextClass) {
        this.audioCtx = new AudioContextClass();
      }
    }
  }

  public async startMic() {
    try {
      this.initContext();
      if (!this.audioCtx) return;
      if (this.audioCtx.state === 'suspended') await this.audioCtx.resume();

      if (!this.micStream) {
        this.micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this.micSource = this.audioCtx.createMediaStreamSource(this.micStream);
        this.micAnalyser = this.audioCtx.createAnalyser();
        this.micAnalyser.fftSize = 256;
        this.micSource.connect(this.micAnalyser);
        this.micDataArray = new Uint8Array(this.micAnalyser.frequencyBinCount);
      }
    } catch (e) {
      console.error("Failed to start mic visualizer", e);
    }
  }

  public stopMic() {
    if (this.micStream) {
      this.micStream.getTracks().forEach(track => track.stop());
      this.micStream = null;
    }
    if (this.micSource) {
      this.micSource.disconnect();
      this.micSource = null;
    }
    this.micAnalyser = null;
    this.micDataArray = null;
  }

  public connectTTS(audioElement: HTMLAudioElement) {
    try {
      this.initContext();
      if (!this.audioCtx) return;
      
      // If we already connected this element, don't do it again
      if ((audioElement as any)._connected) return;
      (audioElement as any)._connected = true;

      const source = this.audioCtx.createMediaElementSource(audioElement);
      this.ttsAnalyser = this.audioCtx.createAnalyser();
      this.ttsAnalyser.fftSize = 256;
      
      source.connect(this.ttsAnalyser);
      this.ttsAnalyser.connect(this.audioCtx.destination);
      
      this.ttsDataArray = new Uint8Array(this.ttsAnalyser.frequencyBinCount);
    } catch (e) {
      console.error("Failed to connect TTS visualizer", e);
    }
  }

  public getMicAmplitude(): number {
    if (!this.micAnalyser || !this.micDataArray) return 0;
    this.micAnalyser.getByteFrequencyData(this.micDataArray);
    let sum = 0;
    for (let i = 0; i < this.micDataArray.length; i++) sum += this.micDataArray[i];
    return sum / this.micDataArray.length / 255.0;
  }

  public getTTSAmplitude(): number {
    if (!this.ttsAnalyser || !this.ttsDataArray) return 0;
    this.ttsAnalyser.getByteFrequencyData(this.ttsDataArray);
    let sum = 0;
    for (let i = 0; i < this.ttsDataArray.length; i++) sum += this.ttsDataArray[i];
    return sum / this.ttsDataArray.length / 255.0;
  }
}

export const visualizer = AudioVisualizer.getInstance();
