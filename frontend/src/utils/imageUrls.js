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

const ALLOWED_IMAGE_EXTENSIONS = new Set([
  'jpg',
  'jpeg',
  'png',
  'webp',
  'gif',
  'avif',
]);

const normalizeExtension = (extension) => {
  if (!extension) {
    return null;
  }
  const lower = extension.toLowerCase();
  if (!ALLOWED_IMAGE_EXTENSIONS.has(lower)) {
    return null;
  }
  return lower === 'jpeg' ? 'jpg' : lower;
};

const inferImageExtension = (imageUrl) => {
  if (!imageUrl) {
    return 'jpg';
  }
  const cleanUrl = imageUrl.split('?')[0].split('#')[0];
  const filename = cleanUrl.split('/').pop() || '';
  if (!filename.includes('.')) {
    return 'jpg';
  }
  const extension = filename.split('.').pop();
  return normalizeExtension(extension) || 'jpg';
};

const buildCanonicalImageFilename = ({ gameId, imageUrl }) => {
  if (!gameId) {
    return null;
  }
  const extension = inferImageExtension(imageUrl);
  return `${gameId}.${extension}`;
};

const buildThumbnailCandidates = ({ gameId }) => {
  if (!gameId) {
    return [];
  }
  const candidates = [];
  if (imageCdnBaseUrl) {
    candidates.push(`${imageCdnBaseUrl}/thumbnails/${gameId}.webp`);
  }
  if (imageLocalBaseUrl) {
    candidates.push(`${imageLocalBaseUrl}/thumbnails/${gameId}.webp`);
  }
  return candidates;
};

const buildOriginalCandidates = ({ gameId, imageUrl, filename, canonicalFilename }) => {
  const candidates = [];

  if (canonicalFilename && imageCdnBaseUrl) {
    candidates.push(`${imageCdnBaseUrl}/games/${canonicalFilename}`);
  } else if (filename && imageCdnBaseUrl) {
    candidates.push(`${imageCdnBaseUrl}/${filename}`);
  }

  if (canonicalFilename && imageLocalBaseUrl) {
    candidates.push(`${imageLocalBaseUrl}/games/${canonicalFilename}`);
  } else if (filename && imageLocalBaseUrl) {
    candidates.push(`${imageLocalBaseUrl}/${filename}`);
  }

  if (gameId) {
    const encodedImageUrl = encodeURIComponent(imageUrl);
    candidates.push(
      `${apiBaseUrl}/images/${gameId}/cached?image_url=${encodedImageUrl}`
    );
  } else if (useImageProxyFallback) {
    candidates.push(`${apiBaseUrl}/proxy-image/${encodeURIComponent(imageUrl)}`);
  } else {
    candidates.push(imageUrl);
  }

  return candidates;
};

export const buildGameImageCandidates = ({ gameId, imageUrl }) => {
  if (!imageUrl) {
    return [];
  }

  const filename = extractImageFilename(imageUrl);
  const canonicalFilename = buildCanonicalImageFilename({ gameId, imageUrl });
  const candidates = [
    ...buildThumbnailCandidates({ gameId }),
    ...buildOriginalCandidates({
      gameId,
      imageUrl,
      filename,
      canonicalFilename,
    }),
  ];
  return [...new Set(candidates)];
};

export const buildGameDetailImageCandidates = ({ gameId, imageUrl }) => {
  if (!imageUrl) {
    return [];
  }
  const filename = extractImageFilename(imageUrl);
  const canonicalFilename = buildCanonicalImageFilename({ gameId, imageUrl });
  const candidates = buildOriginalCandidates({
    gameId,
    imageUrl,
    filename,
    canonicalFilename,
  });
  return [...new Set(candidates)];
};
