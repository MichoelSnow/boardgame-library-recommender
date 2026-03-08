import { apiClient } from './client';

export const fetchMechanics = async () => {
  const response = await apiClient.get('/mechanics/');
  return response.data;
};

export const fetchCategories = async () => {
  const response = await apiClient.get('/categories/');
  return response.data;
};
