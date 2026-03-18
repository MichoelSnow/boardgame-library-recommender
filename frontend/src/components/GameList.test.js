import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import AuthContext from '../context/AuthContext';
import GameList from './GameList';
import { createTestQueryClient, withQueryClient } from '../test/testProviders';

const pageOneGames = {
  games: Array.from({ length: 24 }, (_, index) => ({
    id: index + 1,
    name: `Game ${index + 1}`,
    mechanics: [],
    categories: [],
    suggested_players: [],
    min_players: 2,
    max_players: 4,
    min_playtime: 45,
    max_playtime: 60,
    average_weight: 2.1,
    average: 7.5,
  })),
  total: 48,
};

const pageTwoGames = {
  games: Array.from({ length: 24 }, (_, index) => ({
    id: index + 25,
    name: `Game ${index + 25}`,
    mechanics: [],
    categories: [],
    suggested_players: [],
    min_players: 2,
    max_players: 4,
    min_playtime: 45,
    max_playtime: 60,
    average_weight: 2.1,
    average: 7.5,
  })),
  total: 48,
};

const mockUseGamesQuery = jest.fn();

jest.mock('../hooks/useGameListQueries', () => ({
  useMechanicsQuery: () => ({ data: [] }),
  useCategoriesQuery: () => ({ data: [] }),
  useLibraryGameIdsQuery: () => ({ data: [1, 2, 3, 4, 5] }),
  useCatalogStateQuery: () => ({ data: { state_token: 'token-1' } }),
  useGamesQuery: (params) => mockUseGamesQuery(params),
  useGameDetailsQuery: () => ({ data: null }),
  useConventionKioskStatusQuery: () => ({ data: { convention_mode: false, kiosk_mode: false } }),
}));

jest.mock('../hooks/useRecommendationMutation', () => ({
  useRecommendationMutation: () => ({
    mutateAsync: jest.fn(),
    isPending: false,
  }),
}));

jest.mock('../hooks/useRecommendationSessionState', () => ({
  useRecommendationSessionState: () => ({
    likedGames: [],
    dislikedGames: [],
    hasRecommendations: true,
    showingRecommendations: false,
    recommendationsStale: false,
    allRecommendations: [{ id: 101, name: 'Alpha' }],
    setHasRecommendations: jest.fn(),
    setShowingRecommendations: jest.fn(),
    setRecommendationsStale: jest.fn(),
    setAllRecommendations: jest.fn(),
    likeGame: jest.fn(),
    dislikeGame: jest.fn(),
    resetRecommendationState: jest.fn(),
  }),
}));

describe('GameList', () => {
  const renderGameList = (queryClient = createTestQueryClient()) =>
    render(
      withQueryClient(
        <MemoryRouter>
          <AuthContext.Provider value={{ user: { id: 1, username: 'admin' } }}>
            <GameList />
          </AuthContext.Provider>
        </MemoryRouter>,
        queryClient
      )
    );

  beforeEach(() => {
    mockUseGamesQuery.mockImplementation(({ currentPage }) => ({
      data: currentPage === 2 ? pageTwoGames : pageOneGames,
      isLoading: false,
      error: null,
      isFetching: false,
    }));
  });

  test('closes open filter panel when Show Recommendations is toggled on', async () => {
    renderGameList();

    fireEvent.click(screen.getByRole('button', { name: 'Sort' }));
    expect(screen.getByRole('button', { name: 'Overall Rank' })).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Show Recommendations'));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Overall Rank' })).not.toBeInTheDocument();
    });
  });

  test('resets pagination to page 1 when toggling All Board Games', async () => {
    renderGameList();

    fireEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));

    await waitFor(() => {
      expect(mockUseGamesQuery).toHaveBeenCalledWith(
        expect.objectContaining({ currentPage: 2 })
      );
    });

    fireEvent.click(screen.getByLabelText('All Board Games'));

    await waitFor(() => {
      expect(mockUseGamesQuery).toHaveBeenCalledWith(
        expect.objectContaining({ currentPage: 1, libraryOnly: false })
      );
    });
  });

  test('shows clear search control and clears input when clicked', async () => {
    renderGameList();

    const searchInput = screen.getByLabelText('Search Games');
    fireEvent.change(searchInput, { target: { value: 'Terraforming Mars' } });
    expect(searchInput).toHaveValue('Terraforming Mars');

    fireEvent.click(screen.getByLabelText('Clear search'));
    expect(searchInput).toHaveValue('');
  });

  test('shows per-filter clear control and clears sort filter quickly', async () => {
    renderGameList();

    fireEvent.click(screen.getByRole('button', { name: 'Sort' }));
    fireEvent.click(screen.getByRole('button', { name: 'Name (A-Z)' }));

    expect(screen.getByLabelText('Clear sort filter')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Clear sort filter'));

    await waitFor(() => {
      expect(mockUseGamesQuery).toHaveBeenCalledWith(
        expect.objectContaining({ sortBy: 'rank' })
      );
    });
    expect(screen.queryByLabelText('Clear sort filter')).not.toBeInTheDocument();
  });

  test('Clear All confirms before wiping recommendation state', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(false);

    renderGameList();

    const searchInput = screen.getByLabelText('Search Games');
    fireEvent.change(searchInput, { target: { value: 'Wingspan' } });
    expect(searchInput).toHaveValue('Wingspan');

    fireEvent.click(screen.getByRole('button', { name: 'Clear All' }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(searchInput).toHaveValue('Wingspan');

    confirmSpy.mockReturnValue(true);
    fireEvent.click(screen.getByRole('button', { name: 'Clear All' }));
    expect(searchInput).toHaveValue('');

    confirmSpy.mockRestore();
  });

  test('manual refresh button triggers active catalog query refetch', async () => {
    const queryClient = createTestQueryClient();
    const refetchSpy = jest
      .spyOn(queryClient, 'refetchQueries')
      .mockResolvedValue([]);

    renderGameList(queryClient);

    fireEvent.click(screen.getByRole('button', { name: 'Refresh Catalog' }));

    await waitFor(() => {
      expect(refetchSpy).toHaveBeenCalled();
    });
    expect(refetchSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['games'], type: 'active' })
    );
    expect(refetchSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['library_game_ids'], type: 'active' })
    );
  });
});
