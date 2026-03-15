import { rest } from 'msw';
import { getMswState } from './state';

const API_BASE = '/api';

export const handlers = [
  rest.post(`${API_BASE}/token`, async (req, res, ctx) => {
    const body = await req.text();
    const params = new URLSearchParams(body);
    const username = params.get('username');
    const password = params.get('password');
    const state = getMswState();
    state.tokenRequests += 1;

    if (username === 'demo' && password === 'pass123') {
      return res(ctx.status(200), ctx.json({ access_token: 'token-abc', token_type: 'bearer' }));
    }

    return res(ctx.status(401), ctx.json({ detail: 'Invalid credentials' }));
  }),

  rest.get(`${API_BASE}/users/me/`, (req, res, ctx) => {
    const authHeader = req.headers.get('authorization');
    if (authHeader === 'Bearer token-abc') {
      return res(
        ctx.status(200),
        ctx.json({
          id: 1,
          username: 'demo',
          is_active: true,
          is_admin: false,
        })
      );
    }
    return res(ctx.status(401), ctx.json({ detail: 'Not authenticated' }));
  }),

  rest.get(`${API_BASE}/convention/kiosk/status`, (req, res, ctx) =>
    res(ctx.status(200), ctx.json({ convention_mode: false, kiosk_mode: false }))
  ),

  rest.post(`${API_BASE}/convention/guest-token`, (req, res, ctx) =>
    res(ctx.status(401), ctx.json({ detail: 'Kiosk enrollment is required.' }))
  ),

  rest.get(`${API_BASE}/games/`, (req, res, ctx) => {
    const state = getMswState();
    state.lastGamesQuery = req.url.searchParams.toString();

    if (req.url.searchParams.get('search') === 'trigger-error') {
      return res(ctx.status(500), ctx.json({ detail: 'Server error' }));
    }

    return res(
      ctx.status(200),
      ctx.json({
        games: [
          { id: 101, name: 'Alpha', mechanics: [], categories: [], suggested_players: [] },
        ],
        total: 1,
      })
    );
  }),

  rest.post(`${API_BASE}/recommendations`, async (req, res, ctx) => {
    let payload = {};
    try {
      payload = await req.json();
    } catch (error) {
      return res(ctx.status(400), ctx.json({ detail: 'Invalid recommendation payload' }));
    }
    const state = getMswState();
    state.recommendationRequests.push(payload);

    if ((payload.liked_games || []).includes(999)) {
      return res(ctx.status(500), ctx.json({ detail: 'Recommendation failure' }));
    }

    return res(
      ctx.status(200),
      ctx.json([
        { id: 202, name: 'Rec One' },
        { id: 203, name: 'Rec Two' },
      ])
    );
  }),
];
