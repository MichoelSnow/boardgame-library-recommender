describe('image URL resolver', () => {
  const originalEnv = process.env;

  const loadModule = () => {
    let module;
    jest.isolateModules(() => {
      module = require('./imageUrls');
    });
    return module;
  };

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
    delete process.env.REACT_APP_IMAGE_CDN_BASE_URL;
    delete process.env.REACT_APP_IMAGE_LOCAL_BASE_URL;
    delete process.env.REACT_APP_IMAGE_USE_PROXY_FALLBACK;
    delete process.env.REACT_APP_API_BASE_URL;
    process.env.NODE_ENV = 'development';
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  test('builds local + cache-fill candidates in development defaults', () => {
    const { buildGameImageCandidates } = loadModule();
    const candidates = buildGameImageCandidates({
      gameId: 224517,
      imageUrl: 'https://cf.geekdo-images.com/example/original/img/test-image.jpg',
    });

    expect(candidates[0]).toBe(
      'http://localhost:8000/images/thumbnails/224517.webp'
    );
    expect(candidates[1]).toBe('http://localhost:8000/images/games/224517.jpg');
    expect(candidates[2]).toBe(
      'http://localhost:8000/api/images/224517/cached?image_url=https%3A%2F%2Fcf.geekdo-images.com%2Fexample%2Foriginal%2Fimg%2Ftest-image.jpg'
    );
  });

  test('prefers configured CDN base when provided', () => {
    process.env.REACT_APP_IMAGE_CDN_BASE_URL = 'https://cdn.example.com';
    const { buildGameImageCandidates } = loadModule();
    const candidates = buildGameImageCandidates({
      gameId: 224517,
      imageUrl: 'https://cf.geekdo-images.com/example/original/img/test-image.jpg',
    });

    expect(candidates).toContain(
      'https://cdn.example.com/thumbnails/224517.webp'
    );
    expect(candidates).toContain('https://cdn.example.com/games/224517.jpg');
  });

  test('uses local filename candidate then direct URL when no game id and proxy fallback is disabled', () => {
    process.env.REACT_APP_IMAGE_USE_PROXY_FALLBACK = 'false';
    process.env.REACT_APP_IMAGE_LOCAL_BASE_URL = '';
    process.env.NODE_ENV = 'production';
    const { buildGameImageCandidates } = loadModule();
    const sourceUrl =
      'https://cf.geekdo-images.com/example/original/img/test-image.jpg';
    const candidates = buildGameImageCandidates({
      imageUrl: sourceUrl,
    });

    expect(candidates).toEqual(['/images/test-image.jpg', sourceUrl]);
  });

  test('builds detail candidates with original-first order', () => {
    const { buildGameDetailImageCandidates } = loadModule();
    const candidates = buildGameDetailImageCandidates({
      gameId: 224517,
      imageUrl: 'https://cf.geekdo-images.com/example/original/img/test-image.jpg',
    });

    expect(candidates[0]).toBe('http://localhost:8000/images/games/224517.jpg');
    expect(candidates[1]).toBe(
      'http://localhost:8000/api/images/224517/cached?image_url=https%3A%2F%2Fcf.geekdo-images.com%2Fexample%2Foriginal%2Fimg%2Ftest-image.jpg'
    );
  });

  test('returns no detail candidates when URL is missing', () => {
    const { buildGameDetailImageCandidates } = loadModule();
    expect(buildGameDetailImageCandidates({ gameId: 1, imageUrl: null })).toEqual(
      []
    );
  });
});
