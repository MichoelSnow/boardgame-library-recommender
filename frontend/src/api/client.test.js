import { apiClient, clearAuthToken, setAuthToken } from './client';

jest.mock('axios', () => ({
  create: jest.fn(() => ({
    defaults: {
      headers: {
        common: {},
      },
    },
  })),
}));

describe('api client auth header helpers', () => {
  afterEach(() => {
    clearAuthToken();
  });

  test('setAuthToken sets bearer authorization header', () => {
    setAuthToken('abc123');
    expect(apiClient.defaults.headers.common.Authorization).toBe('Bearer abc123');
  });

  test('clearAuthToken removes authorization header', () => {
    setAuthToken('abc123');
    clearAuthToken();
    expect(apiClient.defaults.headers.common.Authorization).toBeUndefined();
  });
});
