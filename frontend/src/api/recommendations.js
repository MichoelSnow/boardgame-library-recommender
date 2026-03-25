import { apiClient } from './client';

export const createRecommendations = async (payload) => {
  return apiClient.post('/recommendations', payload);
};

export const fetchRecommendationsForGame = async (
  gameId,
  recommenderMode = 'hybrid',
  weightOverrides = {}
) => {
  const params = {
    recommender_mode: recommenderMode,
  };
  if (Number.isFinite(weightOverrides.collaborativeWeight)) {
    params.collaborative_weight = weightOverrides.collaborativeWeight;
  }
  if (Number.isFinite(weightOverrides.contentWeight)) {
    params.content_weight = weightOverrides.contentWeight;
  }
  if (Number.isFinite(weightOverrides.qualityWeight)) {
    params.quality_weight = weightOverrides.qualityWeight;
  }
  return apiClient.get(`/recommendations/${gameId}`, {
    params,
  });
};
