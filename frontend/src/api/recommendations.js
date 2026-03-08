import { apiClient } from './client';

export const createRecommendations = async (payload) => {
  return apiClient.post('/recommendations', payload);
};

export const fetchRecommendationsForGame = async (gameId) => {
  return apiClient.get(`/recommendations/${gameId}`);
};
