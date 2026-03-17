import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import AuthContext from '../context/AuthContext';
import GameList from './GameList';
import { withQueryClient } from '../test/testProviders';

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
  const renderGameList = () =>
    render(
      withQueryClient(
        <MemoryRouter>
          <AuthContext.Provider value={{ user: { id: 1, username: 'admin' } }}>
            <GameList />
          </AuthContext.Provider>
        </MemoryRouter>
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
    const user = userEvent.setup();

    renderGameList();

    await user.click(screen.getByRole('button', { name: 'Sort' }));
    expect(screen.getByRole('button', { name: 'Overall Rank' })).toBeInTheDocument();

    await user.click(screen.getByLabelText('Show Recommendations'));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Overall Rank' })).not.toBeInTheDocument();
    });
  });

  test('resets pagination to page 1 when toggling All Board Games', async () => {
    const user = userEvent.setup();

    renderGameList();

    await user.click(screen.getByRole('button', { name: 'Go to page 2' }));

    await waitFor(() => {
      expect(mockUseGamesQuery).toHaveBeenCalledWith(
        expect.objectContaining({ currentPage: 2 })
      );
    });

    await user.click(screen.getByLabelText('All Board Games'));

    await waitFor(() => {
      expect(mockUseGamesQuery).toHaveBeenCalledWith(
        expect.objectContaining({ currentPage: 1, libraryOnly: false })
      );
    });
  });
});
