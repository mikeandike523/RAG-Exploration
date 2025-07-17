export class FileStreamer {
  private reader: ReadableStreamDefaultReader<Uint8Array>;
  private buffer = new Uint8Array(0);
  private loadedPointer = 0;
  private finishedPointer = 0;
  private chunkSize: number
  private onChunk: (chunk: Blob, offset: number)=>Promise<void>

  constructor(
    file: File,
    chunkSize: number,
    onChunk: (
      chunk: Blob,
      offset: number
    ) => Promise<void>
  ) {
    this.chunkSize = chunkSize
    this.reader = file.stream().getReader();
    this.onChunk = onChunk
  }

  /** 
   * Start reading the file, splitting into ≤ chunkSize blobs,
   * and calling onChunk(blob, offset) for each slice
   */
  async run(): Promise<void> {
    while (true) {
      const { done, value } = await this.reader.read();
      if (done) break;
      if (!value) continue;

      // absorb OS‑chunk
      this.loadedPointer += value.length;
      const tmp = new Uint8Array(this.buffer.length + value.length);
      tmp.set(this.buffer, 0);
      tmp.set(value, this.buffer.length);
      this.buffer = tmp;

      // flush out full chunkSize slices
      while (this.buffer.length >= this.chunkSize) {
        const slice = this.buffer.subarray(0, this.chunkSize);
        const blob = new Blob([slice]);
        await this.onChunk(blob, this.finishedPointer);

        this.finishedPointer += slice.length;
        this.buffer = this.buffer.subarray(slice.length);
      }
    }

    // flush any remaining bytes
    if (this.buffer.length > 0) {
      const finalBlob = new Blob([this.buffer]);
      await this.onChunk(finalBlob, this.finishedPointer);
      this.finishedPointer += this.buffer.length;
      this.buffer = new Uint8Array(0);
    }
  }
}