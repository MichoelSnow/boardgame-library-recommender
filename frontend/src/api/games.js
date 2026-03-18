import { apiClient } from './client';

export const fetchGames = async (params) => {
  const response = await apiClient.get('/games/', { params });
  return response.data;
};

export const fetchGameDetails = async (gameId) => {
  const response = await apiClient.get(`/games/${gameId}/`);
  return response.data;
};

export const fetchLibraryGameIds = async () => {
  const response = await apiClient.get('/library_game_ids/');
  return response.data;
};

export const fetchCatalogState = async () => {
  const response = await apiClient.get('/catalog/state');
  return response.data;
};
