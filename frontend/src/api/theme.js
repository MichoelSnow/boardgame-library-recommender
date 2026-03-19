import { apiClient } from './client';

export const fetchThemeSettings = async () => {
  const response = await apiClient.get('/theme');
  return response.data;
};

export const updateThemeSettings = async ({
  primaryColor,
  libraryName,
} = {}) => {
  const payload = {};
  if (primaryColor !== undefined) {
    payload.primary_color = primaryColor;
  }
  if (libraryName !== undefined) {
    payload.library_name = libraryName;
  }
  const response = await apiClient.put('/admin/theme', payload);
  return response.data;
};
