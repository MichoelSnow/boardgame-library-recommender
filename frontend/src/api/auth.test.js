import { fetchCurrentUser, loginWithPassword } from './auth';
import { apiClient } from './client';

jest.mock('./client', () => ({
  apiClient: {
    post: jest.fn(),
    get: jest.fn(),
  },
}));

describe('auth api', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('loginWithPassword sends form-encoded request with grant_type=password', async () => {
    apiClient.post.mockResolvedValue({ data: { access_token: 'token' } });

    const response = await loginWithPassword('alice', 'secret');

    expect(apiClient.post).toHaveBeenCalledTimes(1);
    const [path, payload, options] = apiClient.post.mock.calls[0];
    expect(path).toBe('/token');
    expect(options).toEqual({
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    expect(payload).toBeInstanceOf(URLSearchParams);
    expect(payload.get('username')).toBe('alice');
    expect(payload.get('password')).toBe('secret');
    expect(payload.get('grant_type')).toBe('password');
    expect(response).toEqual({ access_token: 'token' });
  });

  test('fetchCurrentUser returns parsed response payload', async () => {
    apiClient.get.mockResolvedValue({ data: { username: 'alice' } });

    const response = await fetchCurrentUser();

    expect(apiClient.get).toHaveBeenCalledWith('/users/me/');
    expect(response).toEqual({ username: 'alice' });
  });
});
