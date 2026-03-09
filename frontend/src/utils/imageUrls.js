import {
  apiBaseUrl,
  imageCdnBaseUrl,
  imageLocalBaseUrl,
  useImageProxyFallback,
} from '../config';

export const extractImageFilename = (imageUrl) => {
  if (!imageUrl) {
    return null;
  }
  const segments = imageUrl.split('/');
  const lastSegment = segments[segments.length - 1];
  return lastSegment || null;
};

export const buildGameImageCandidates = ({ gameId, imageUrl }) => {
  if (!imageUrl) {
    return [];
  }

  const candidates = [];
  const filename = extractImageFilename(imageUrl);

  if (filename && imageCdnBaseUrl) {
    candidates.push(`${imageCdnBaseUrl}/${filename}`);
  }

  if (filename && imageLocalBaseUrl) {
    candidates.push(`${imageLocalBaseUrl}/${filename}`);
  }

  if (gameId) {
    candidates.push(`${apiBaseUrl}/images/${gameId}/cached`);
  } else if (useImageProxyFallback) {
    candidates.push(`${apiBaseUrl}/proxy-image/${encodeURIComponent(imageUrl)}`);
  } else {
    candidates.push(imageUrl);
  }

  return [...new Set(candidates)];
};

export const resolveGameDetailImageUrl = ({ gameId, imageUrl }) => {
  const [primary] = buildGameImageCandidates({ gameId, imageUrl });
  return primary || null;
};
