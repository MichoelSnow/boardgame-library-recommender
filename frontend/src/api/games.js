import { apiClient } from './client';

export const fetchGames = async (params) => {
  const response = await apiClient.get('/games/', { params });
  return response.data;
};

export const fetchGameDetails = async (gameId) => {
  const response = await apiClient.get(`/games/${gameId}/`);
  return response.data;
};

export const fetchPaxGameIds = async () => {
  const response = await apiClient.get('/pax_game_ids/');
  return response.data;
};
