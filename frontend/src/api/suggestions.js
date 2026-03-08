import { apiClient } from './client';

export const createSuggestion = async (comment) => {
  const response = await apiClient.post('/suggestions/', { comment });
  return response.data;
};
