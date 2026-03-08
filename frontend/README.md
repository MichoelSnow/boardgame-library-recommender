# Frontend

## Scope
- React SPA for catalog browsing, auth flows, recommendation interactions, and settings.

## Key Paths
- `src/components/`: reusable UI components.
- `src/context/`: auth/session state providers.
- `src/pages/`: route/page-level components.
- `src/services/`: API request layer.
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
