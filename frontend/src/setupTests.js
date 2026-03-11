import '@testing-library/jest-dom';
import { server } from './test/msw/server';
import { resetMswState } from './test/msw/state';

jest.mock('axios');

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
});

afterEach(() => {
  server.resetHandlers();
  resetMswState();
  localStorage.clear();
});

afterAll(() => {
  server.close();
});
