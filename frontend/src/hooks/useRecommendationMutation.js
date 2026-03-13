import { useMutation } from '@tanstack/react-query';
import { createRecommendations } from '../api/recommendations';

export const useRecommendationMutation = () =>
  useMutation({
    mutationFn: ({ likedGames, dislikedGames, limit = 50, libraryOnly = false }) =>
      createRecommendations({
        liked_games: likedGames,
        disliked_games: dislikedGames,
        limit,
        library_only: libraryOnly,
      }),
  });
