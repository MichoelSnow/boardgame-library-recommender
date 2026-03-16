import { apiClient } from './client';

export const fetchThemeSettings = async () => {
  const response = await apiClient.get('/theme');
  return response.data;
};

export const updateThemeSettings = async (primaryColor) => {
  const response = await apiClient.put('/admin/theme', {
    primary_color: primaryColor,
  });
  return response.data;
};
