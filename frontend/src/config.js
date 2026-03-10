const environment = process.env.NODE_ENV || 'development';
const isDevelopment = environment === 'development';

const normalizeUrl = (value) => {
  if (!value) {
    return null;
  }
  return value.replace(/\/+$/, '');
};

export const apiBaseUrl = normalizeUrl(
  process.env.REACT_APP_API_BASE_URL ||
    (isDevelopment ? 'http://localhost:8000/api' : '/api')
);

// Optional local image mount (for development/local volume use).
export const imageLocalBaseUrl = normalizeUrl(
  process.env.REACT_APP_IMAGE_LOCAL_BASE_URL ||
    (isDevelopment ? 'http://localhost:8000/images' : '/images')
);

// Optional CDN base URL (backup path; primary runtime is fly_local).
export const imageCdnBaseUrl = normalizeUrl(
  process.env.REACT_APP_IMAGE_CDN_BASE_URL || ''
);

// Keep proxy fallback enabled by default as a resilience safety net.
export const useImageProxyFallback =
  (process.env.REACT_APP_IMAGE_USE_PROXY_FALLBACK || 'true').toLowerCase() ===
  'true';

export const placeholderImagePath =
  process.env.REACT_APP_IMAGE_PLACEHOLDER || '/assets/images/game-placeholder.svg';
