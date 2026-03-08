import { apiClient } from './client';

export const changeCurrentUserPassword = async (payload) => {
  const response = await apiClient.put('/users/me/password', payload);
  return response.data;
};
