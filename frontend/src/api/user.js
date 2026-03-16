import { apiClient } from './client';

export const changeCurrentUserPassword = async (payload) => {
  const response = await apiClient.put('/users/me/password', payload);
  return response.data;
};

export const fetchAdminUsers = async () => {
  const response = await apiClient.get('/admin/users');
  return response.data;
};

export const createAdminUser = async (payload) => {
  const response = await apiClient.post('/users/', payload);
  return response.data;
};

export const updateAdminUser = async (userId, payload) => {
  const response = await apiClient.put(`/admin/users/${userId}`, payload);
  return response.data;
};

export const resetAdminUserPassword = async (userId, newPassword) => {
  const response = await apiClient.put(`/admin/users/${userId}/password`, {
    new_password: newPassword,
  });
  return response.data;
};
