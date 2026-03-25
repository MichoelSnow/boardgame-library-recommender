import { useQuery } from '@tanstack/react-query';
import { fetchCategories, fetchMechanics } from '../api/filters';
import {
  fetchCatalogState,
  fetchGameDetails,
  fetchGames,
  fetchLibraryGameIds,
} from '../api/games';
import { fetchRecommendationsForGame } from '../api/recommendations';
import { fetchConventionKioskStatus } from '../api/convention';

const CATALOG_STATE_POLL_INTERVAL_MS = 60 * 1000;

export const useMechanicsQuery = () =>
  useQuery({
    queryKey: ['mechanics_alphabetically'],
    queryFn: fetchMechanics,
    staleTime: 24 * 60 * 60 * 1000,
  });

export const useCategoriesQuery = () =>
  useQuery({
    queryKey: ['categories_alphabetically'],
    queryFn: fetchCategories,
    staleTime: 24 * 60 * 60 * 1000,
  });

export const useGamesQuery = ({
  gamesPerPage,
  currentPage,
  sortBy,
  libraryOnly,
  searchTerm,
  playerOptions,
  selectedDesigners,
  selectedArtists,
  selectedMechanicIds,
  selectedCategoryIds,
  weight,
  isRecommendation,
}) =>
  useQuery({
    queryKey: [
      'games',
      searchTerm,
      playerOptions,
      selectedDesigners,
      selectedArtists,
      selectedMechanicIds,
      selectedCategoryIds,
      weight,
      sortBy,
      currentPage,
      libraryOnly,
    ],
    queryFn: async () => {
      const params = {
        limit: gamesPerPage,
        skip: (currentPage - 1) * gamesPerPage,
        sort_by: sortBy,
        library_only: libraryOnly,
      };

      if (searchTerm) params.search = searchTerm;

      if (playerOptions.count) {
        params.players = playerOptions.count;
        if (playerOptions.recommendation && playerOptions.recommendation !== 'allowed') {
          params.recommendations = playerOptions.recommendation;
        }
      }

      if (selectedDesigners.length > 0) {
        params.designer_id = selectedDesigners.map((d) => d.boardgamedesigner_id).join(',');
      }

      if (selectedArtists.length > 0) {
        params.artist_id = selectedArtists.map((a) => a.boardgameartist_id).join(',');
      }

      if (selectedMechanicIds.length > 0) {
        params.mechanics = selectedMechanicIds.join(',');
      }

      if (selectedCategoryIds.length > 0) {
        params.categories = selectedCategoryIds.join(',');
      }

      const activeWeights = Object.entries(weight)
        .filter(([, checked]) => checked)
        .map(([key]) => key);

      if (activeWeights.length > 0) {
        params.weight = activeWeights.join(',');
      }

      return fetchGames(params);
    },
    keepPreviousData: true,
    enabled: !isRecommendation,
    staleTime: 30 * 1000,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
    refetchInterval: false,
  });

export const useLibraryGameIdsQuery = () =>
  useQuery({
    queryKey: ['library_game_ids'],
    queryFn: fetchLibraryGameIds,
    staleTime: 30 * 1000,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
    refetchInterval: false,
  });

export const useCatalogStateQuery = () =>
  useQuery({
    queryKey: ['catalog_state'],
    queryFn: fetchCatalogState,
    staleTime: 30 * 1000,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
    refetchInterval: CATALOG_STATE_POLL_INTERVAL_MS,
  });

export const useGameDetailsQuery = ({ gameId, enabled }) =>
  useQuery({
    queryKey: ['game_details', gameId],
    queryFn: () => fetchGameDetails(gameId),
    enabled: Boolean(gameId) && enabled,
    staleTime: 10 * 60 * 1000,
  });

export const useGameRecommendationsQuery = ({
  gameId,
  enabled,
  recommenderMode = 'hybrid',
}) =>
  useQuery({
    queryKey: ['game_recommendations', gameId, recommenderMode],
    queryFn: () => fetchRecommendationsForGame(gameId, recommenderMode),
    enabled: Boolean(gameId) && enabled,
    staleTime: 5 * 60 * 1000,
  });

export const useConventionKioskStatusQuery = () =>
  useQuery({
    queryKey: ['convention_kiosk_status'],
    queryFn: fetchConventionKioskStatus,
    staleTime: 30 * 1000,
    retry: false,
  });
