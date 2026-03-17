const LIKELY_MOJIBAKE_PATTERN =
  /[\u0080-\u009f]|[ÃÂâð]|(?:æ.|œ.)|(?:ã.)|(?:å.)/;
const MOJIBAKE_MARKER_PATTERN = /[\u0080-\u009fÃÂâðæœã]/g;
const CP1252_REVERSE_MAP = new Map([
  [0x20ac, 0x80],
  [0x201a, 0x82],
  [0x0192, 0x83],
  [0x201e, 0x84],
  [0x2026, 0x85],
  [0x2020, 0x86],
  [0x2021, 0x87],
  [0x02c6, 0x88],
  [0x2030, 0x89],
  [0x0160, 0x8a],
  [0x2039, 0x8b],
  [0x0152, 0x8c],
  [0x017d, 0x8e],
  [0x2018, 0x91],
  [0x2019, 0x92],
  [0x201c, 0x93],
  [0x201d, 0x94],
  [0x2022, 0x95],
  [0x2013, 0x96],
  [0x2014, 0x97],
  [0x02dc, 0x98],
  [0x2122, 0x99],
  [0x0161, 0x9a],
  [0x203a, 0x9b],
  [0x0153, 0x9c],
  [0x017e, 0x9e],
  [0x0178, 0x9f],
]);

const toByte = (character) => {
  const codePoint = character.codePointAt(0);
  if (codePoint === undefined) {
    return null;
  }
  if (codePoint <= 0xff) {
    return codePoint;
  }
  if (CP1252_REVERSE_MAP.has(codePoint)) {
    return CP1252_REVERSE_MAP.get(codePoint);
  }
  return null;
};

const countMojibakeMarkers = (value) =>
  (value.match(MOJIBAKE_MARKER_PATTERN) || []).length;

const isBetterOrEquivalentDecode = (original, candidate) =>
  candidate !== original &&
  countMojibakeMarkers(candidate) <= countMojibakeMarkers(original);

const utf8ExpectedLength = (firstByte) => {
  if ((firstByte & 0b10000000) === 0) {
    return 1;
  }
  if ((firstByte & 0b11100000) === 0b11000000) {
    return 2;
  }
  if ((firstByte & 0b11110000) === 0b11100000) {
    return 3;
  }
  if ((firstByte & 0b11111000) === 0b11110000) {
    return 4;
  }
  return null;
};

const tryDecodePercentUtf8 = (bytes) => {
  const percentEncoded = Array.from(
    bytes,
    (byteValue) => `%${byteValue.toString(16).padStart(2, '0')}`
  ).join('');
  return decodeURIComponent(percentEncoded);
};

const repairIncompleteTrailingUtf8 = (bytes) => {
  if (!bytes.length) {
    return null;
  }

  let continuationCount = 0;
  for (let index = bytes.length - 1; index >= 0; index -= 1) {
    const value = bytes[index];
    if ((value & 0b11000000) === 0b10000000) {
      continuationCount += 1;
      continue;
    }

    const expectedLength = utf8ExpectedLength(value);
    if (!expectedLength || expectedLength <= 1) {
      return null;
    }

    const presentLength = continuationCount + 1;
    if (presentLength >= expectedLength) {
      return null;
    }

    if (expectedLength - presentLength !== 1) {
      return null;
    }

    const preferredContinuationBytes = [
      0xa0,
      ...Array.from({ length: 64 }, (_unused, offset) => 0x80 + offset),
    ];
    for (const continuationByte of preferredContinuationBytes) {
      try {
        return tryDecodePercentUtf8(Uint8Array.from([...bytes, continuationByte]));
      } catch (_error) {
        // Try next continuation candidate.
      }
    }
    return null;
  }

  return null;
};

const attemptUtf8Repair = (value) => {
  try {
    const bytes = Uint8Array.from(
      Array.from(value, (character) => {
        const mappedByte = toByte(character);
        if (mappedByte === null) {
          throw new Error('character is not representable as latin-1/cp1252 byte');
        }
        return mappedByte;
      })
    );
    try {
      return tryDecodePercentUtf8(bytes);
    } catch (_decodeError) {
      const trailingRepair = repairIncompleteTrailingUtf8(bytes);
      if (trailingRepair) {
        return trailingRepair;
      }
      if (typeof TextDecoder !== 'undefined') {
        try {
          const tolerantDecoded = new TextDecoder('utf-8', {
            fatal: false,
          }).decode(bytes);
          const withoutReplacement = tolerantDecoded.replace(/\uFFFD/g, '');
          if (
            countMojibakeMarkers(withoutReplacement) <
            countMojibakeMarkers(value)
          ) {
            return withoutReplacement;
          }
        } catch (_tolerantDecodeError) {
          // Continue to null fallback.
        }
      }
      return null;
    }
  } catch (_error) {
    return null;
  }
};

const repairWhitespaceSplitByteRuns = (text) => {
  let updated = text;
  const splitByteRunPattern =
    /([^\s]*[ÃÂâðæœã][^\s]*)\s+([\u00a0-\u00bf][^\s]*)/g;

  for (let attempt = 0; attempt < 3; attempt += 1) {
    let changed = false;
    updated = updated.replace(splitByteRunPattern, (full, left, right) => {
      const joined = `${left}${right}`;
      const repairedJoined = attemptUtf8Repair(joined);
      if (
        repairedJoined &&
        isBetterOrEquivalentDecode(joined, repairedJoined)
      ) {
        changed = true;
        return repairedJoined;
      }
      return full;
    });
    if (!changed) {
      break;
    }
  }

  return updated;
};

export const repairMojibake = (text) => {
  if (!text || !LIKELY_MOJIBAKE_PATTERN.test(text)) {
    return text || '';
  }

  const repairedWhole = attemptUtf8Repair(text);
  if (
    repairedWhole &&
    isBetterOrEquivalentDecode(text, repairedWhole)
  ) {
    return repairedWhole;
  }

  const splitRunsRepaired = repairWhitespaceSplitByteRuns(text);

  return splitRunsRepaired.replace(/\S+/g, (token) => {
    if (!LIKELY_MOJIBAKE_PATTERN.test(token)) {
      return token;
    }
    const repairedToken = attemptUtf8Repair(token);
    if (repairedToken) {
      return isBetterOrEquivalentDecode(token, repairedToken)
        ? repairedToken
        : token;
    }

    let rebuilt = '';
    let byteChunk = '';

    const flushByteChunk = () => {
      if (!byteChunk) {
        return;
      }
      if (!LIKELY_MOJIBAKE_PATTERN.test(byteChunk)) {
        rebuilt += byteChunk;
        byteChunk = '';
        return;
      }
      const repairedByteChunk = attemptUtf8Repair(byteChunk);
      if (
        repairedByteChunk &&
        isBetterOrEquivalentDecode(byteChunk, repairedByteChunk)
      ) {
        rebuilt += repairedByteChunk;
      } else {
        rebuilt += byteChunk;
      }
      byteChunk = '';
    };

    for (const character of token) {
      if (toByte(character) !== null) {
        byteChunk += character;
        continue;
      }
      flushByteChunk();
      rebuilt += character;
    }
    flushByteChunk();
    return rebuilt;
  });
};

export const decodeGameDescription = (text) => {
  if (!text) {
    return '';
  }

  const textarea = document.createElement('textarea');
  textarea.innerHTML = text;

  const decoded = textarea.value
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/&#10;/g, '\n')
    .replace(/&#13;/g, '\n')
    .replace(/&nbsp;/g, ' ');

  let repaired = decoded;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const next = repairMojibake(repaired);
    if (next === repaired) {
      break;
    }
    repaired = next;
  }

  return repaired;
};
