import { useMutation } from '@tanstack/react-query';
import { createRecommendations } from '../api/recommendations';

export const useRecommendationMutation = () =>
  useMutation({
    mutationFn: ({
      likedGames,
      dislikedGames,
      limit = 50,
      libraryOnly = false,
      recommenderMode,
      collaborativeWeight,
      contentWeight,
      qualityWeight,
    }) => {
      const payload = {
        liked_games: likedGames,
        disliked_games: dislikedGames,
        limit,
        library_only: libraryOnly,
      };
      if (recommenderMode) {
        payload.recommender_mode = recommenderMode;
      }
      if (Number.isFinite(collaborativeWeight)) {
        payload.collaborative_weight = collaborativeWeight;
      }
      if (Number.isFinite(contentWeight)) {
        payload.content_weight = contentWeight;
      }
      if (Number.isFinite(qualityWeight)) {
        payload.quality_weight = qualityWeight;
      }
      return createRecommendations(payload);
    },
  });
