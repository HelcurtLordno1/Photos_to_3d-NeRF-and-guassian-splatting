/// <reference lib="webworker" />
// Decode the pinned binary little-endian PLY without per-vertex objects.
self.onmessage = async (
  event: MessageEvent<{
    url: string;
    maxVertices: number;
    maxBytes: number;
  }>,
) => {
  try {
    const response = await fetch(event.data.url);
    if (!response.ok) throw new Error('Point cloud download failed');
    const length = Number(response.headers.get('Content-Length'));
    if (length > event.data.maxBytes) throw new Error('Decode memory budget exceeded');
    const buffer = await response.arrayBuffer();
    if (buffer.byteLength > event.data.maxBytes) throw new Error('Decode memory budget exceeded');
    const bytes = new Uint8Array(buffer);
    const marker = new TextEncoder().encode('end_header');
    let end = -1;
    for (let i = 0; i < Math.min(bytes.length, 65536); i++) {
      if (marker.every((n, k) => bytes[i + k] === n)) {
        end = i + marker.length;
        break;
      }
    }
    if (end < 0) throw new Error('PLY header missing');
    while (bytes[end] === 13 || bytes[end] === 10) end++;
    const header = new TextDecoder().decode(bytes.subarray(0, end));
    if (!header.includes('format binary_little_endian 1.0'))
      throw new Error('Unsupported PLY format');
    const count = Number(header.match(/element vertex (\d+)/)?.[1]);
    if (!count || count > event.data.maxVertices) throw new Error('Vertex budget exceeded');
    const properties = [...header.matchAll(/property (\w+) (\w+)/g)];
    const types: Record<string, number> = { float: 4, float32: 4, double: 8, uchar: 1, uint8: 1 };
    let stride = 0;
    const offsets: Record<
      string,
      {
        offset: number;
        type: string;
      }
    > = {};
    for (const p of properties) {
      if (!types[p[1]]) throw new Error('Unsupported PLY property');
      offsets[p[2]] = { offset: stride, type: p[1] };
      stride += types[p[1]];
    }
    if (buffer.byteLength < end + count * stride) throw new Error('Truncated PLY');
    const view = new DataView(buffer);
    const position = new Float32Array(count * 3);
    const color = new Float32Array(count * 3);
    const read = (base: number, key: string) => {
      const p = offsets[key];
      if (!p) throw new Error('Required PLY field missing');
      return p.type === 'uchar' || p.type === 'uint8'
        ? view.getUint8(base + p.offset)
        : p.type === 'double'
          ? view.getFloat64(base + p.offset, true)
          : view.getFloat32(base + p.offset, true);
    };
    for (let i = 0; i < count; i++) {
      const base = end + i * stride;
      for (let k = 0; k < 3; k++) {
        position[i * 3 + k] = read(base, ['x', 'y', 'z'][k]);
        const srgb = read(base, ['red', 'green', 'blue'][k]) / 255;
        color[i * 3 + k] = srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
      }
    }
    self.postMessage({ position, color, count }, [position.buffer, color.buffer]);
  } catch (error) {
    self.postMessage({ error: String(error) });
  }
};
