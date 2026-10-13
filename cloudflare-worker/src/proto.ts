/**
 * Lightweight pure-TypeScript Protobuf decoder and gRPC wire formatter
 * Zero external dependencies.
 */

export function decodeProtobuf(data: Uint8Array): Record<number, any> {
  let idx = 0;
  const fields: Record<number, any> = {};

  while (idx < data.length) {
    let key = 0;
    let shift = 0;
    while (idx < data.length) {
      const b = data[idx++];
      key |= (b & 0x7f) << shift;
      if (!(b & 0x80)) break;
      shift += 7;
    }
    if (key === 0) break;

    const fieldNum = key >> 3;
    const wireType = key & 0x07;

    let val: any;

    if (wireType === 0) {
      // Varint
      let v = 0;
      let s = 0;
      while (idx < data.length) {
        const b = data[idx++];
        v |= (b & 0x7f) << s;
        if (!(b & 0x80)) break;
        s += 7;
      }
      val = v;
    } else if (wireType === 1) {
      // 64-bit
      val = data.slice(idx, idx + 8);
      idx += 8;
    } else if (wireType === 2) {
      // Length-delimited
      let length = 0;
      let s = 0;
      while (idx < data.length) {
        const b = data[idx++];
        length |= (b & 0x7f) << s;
        if (!(b & 0x80)) break;
        s += 7;
      }
      const raw = data.slice(idx, idx + length);
      idx += length;

      try {
        const decoder = new TextDecoder("utf-8");
        const str = decoder.decode(raw);
        if ([...str].every((c) => c.charCodeAt(0) >= 32 || c === "\n" || c === "\r" || c === "\t")) {
          val = str;
        } else {
          val = decodeProtobuf(raw);
        }
      } catch {
        try {
          val = decodeProtobuf(raw);
        } catch {
          val = raw;
        }
      }
    } else if (wireType === 5) {
      // 32-bit
      val = data.slice(idx, idx + 4);
      idx += 4;
    } else {
      break;
    }

    if (fields[fieldNum] === undefined) {
      fields[fieldNum] = val;
    } else if (Array.isArray(fields[fieldNum])) {
      fields[fieldNum].push(val);
    } else {
      fields[fieldNum] = [fields[fieldNum], val];
    }
  }

  return fields;
}

export function encodeGrpcFrame(payload: Uint8Array): Uint8Array {
  const frame = new Uint8Array(5 + payload.length);
  frame[0] = 0; // Flags: 0 = uncompressed
  const len = payload.length;
  frame[1] = (len >> 24) & 0xff;
  frame[2] = (len >> 16) & 0xff;
  frame[3] = (len >> 8) & 0xff;
  frame[4] = len & 0xff;
  frame.set(payload, 5);
  return frame;
}

export function decodeGrpcFrame(frame: Uint8Array): Uint8Array {
  if (frame.length <= 5) return new Uint8Array();
  return frame.slice(5);
}
