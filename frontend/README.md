# Frontend

## Scope
- React SPA for catalog browsing, auth flows, recommendation interactions, and settings.

## Key Paths
- `src/api/`: canonical API layer modules (endpoint ownership + request shaping).
- `src/components/`: reusable UI components.
- `src/context/`: auth/session state providers.
- `src/pages/`: route/page-level components.
- `public/`: static assets.

## Development
Install dependencies:
```bash
cd frontend
npm ci
```

Start dev server:
```bash
npm start
```

### Development Server Notes
- Runs at `http://localhost:3000`
- Hot-reload on source changes
- Uses backend API configuration from frontend service/config code
- Auth/session state is managed through React context

## Build
```bash
npm run build
```

## Tests
```bash
npm test
```

## Environment Notes
- API base behavior is configured in frontend code and deployment config.
- For deployed environments, verify requests resolve to the expected app host (`dev` vs `prod`) before smoke testing.
- Kiosk-device behavior is determined at runtime from backend kiosk enrollment status (`/api/convention/kiosk/status`), not by a frontend build-time flag.
- Image delivery supports staged migration via optional environment variables:
  - `REACT_APP_IMAGE_CDN_BASE_URL`: CDN base URL (for R2-backed images), e.g. `https://cdn.example.com/games`
  - `REACT_APP_IMAGE_LOCAL_BASE_URL`: local mounted image base (defaults to `http://localhost:8000/images` in development)
  - `REACT_APP_IMAGE_USE_PROXY_FALLBACK`: `true|false` (default `true`) to keep or disable backend proxy fallback
  - `REACT_APP_IMAGE_PLACEHOLDER`: placeholder image path (default `/assets/images/game-placeholder.svg`)
