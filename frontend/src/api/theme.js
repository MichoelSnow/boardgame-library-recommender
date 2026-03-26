import { apiClient } from './client';

export const fetchThemeSettings = async () => {
  const response = await apiClient.get('/theme');
  return response.data;
};

export const updateThemeSettings = async ({
  primaryColor,
  libraryName,
  collaborativeWeight,
  contentWeight,
  qualityWeight,
} = {}) => {
  const payload = {};
  if (primaryColor !== undefined) {
    payload.primary_color = primaryColor;
  }
  if (libraryName !== undefined) {
    payload.library_name = libraryName;
  }
  if (collaborativeWeight !== undefined) {
    payload.collaborative_weight = collaborativeWeight;
  }
  if (contentWeight !== undefined) {
    payload.content_weight = contentWeight;
  }
  if (qualityWeight !== undefined) {
    payload.quality_weight = qualityWeight;
  }
  const response = await apiClient.put('/admin/theme', payload);
  return response.data;
};
