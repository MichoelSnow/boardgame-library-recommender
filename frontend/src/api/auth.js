import { apiClient } from './client';

export const loginWithPassword = async (username, password) => {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);
  formData.append('grant_type', 'password');

  const response = await apiClient.post('/token', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });

  return response.data;
};

export const fetchCurrentUser = async () => {
  const response = await apiClient.get('/users/me/');
  return response.data;
};

export const fetchConventionGuestToken = async () => {
  const response = await apiClient.post('/convention/guest-token');
  return response.data;
};
