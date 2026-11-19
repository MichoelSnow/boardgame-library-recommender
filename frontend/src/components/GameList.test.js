import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import {
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import AuthContext from '../context/AuthContext';
import GameList from './GameList';
import { createTestQueryClient, withQueryClient } from '../test/testProviders';

const mockUseGamesQuery = jest.fn();
const mockUseFilterTaxonomyQuery = jest.fn();
const mockUseGameDetailsQuery = jest.fn();

jest.mock('./GameDetails', () => ({
  __esModule: true,
  default: ({ onFilter, selectedCategoryIds }) => (
    <div>
      <button
        type="button"
        aria-pressed={selectedCategoryIds.includes(1030)}
        onClick={() => onFilter('category', 1030, 'Party Game')}
      >
        Party Game detail
      </button>
    </div>
  ),
}));

jest.mock('../hooks/useGameListQueries', () => ({
  useMechanicsQuery: () => ({ data: [] }),
  useCategoriesQuery: () => ({ data: [] }),
  useFilterTaxonomyQuery: () => mockUseFilterTaxonomyQuery(),
  useLibraryGameIdsQuery: () => ({ data: [] }),
  useCatalogStateQuery: () => ({ data: { state_token: 'token-1' } }),
  useGamesQuery: (params) => mockUseGamesQuery(params),
  useGameDetailsQuery: () => mockUseGameDetailsQuery(),
  useConventionKioskStatusQuery: () => ({ data: { kiosk_mode: false } }),
}));

jest.mock('../hooks/useRecommendationMutation', () => ({
  useRecommendationMutation: () => ({ mutateAsync: jest.fn(), isPending: false }),
}));

jest.mock('../hooks/useRecommendationSessionState', () => ({
  useRecommendationSessionState: () => ({
    likedGames: [],
    dislikedGames: [],
    hasRecommendations: false,
    showingRecommendations: false,
    recommendationsStale: false,
    allRecommendations: [],
    setHasRecommendations: jest.fn(),
    setShowingRecommendations: jest.fn(),
    setRecommendationsStale: jest.fn(),
    setAllRecommendations: jest.fn(),
    likeGame: jest.fn(),
    dislikeGame: jest.fn(),
    resetRecommendationState: jest.fn(),
  }),
}));

const renderGameList = (initialEntries = ['/']) =>
  render(
    withQueryClient(
      <MemoryRouter initialEntries={initialEntries}>
        <AuthContext.Provider value={{ user: { id: 1, username: 'admin' } }}>
          <GameList />
        </AuthContext.Provider>
      </MemoryRouter>,
      createTestQueryClient()
    )
  );

describe('GameList browse shell', () => {
  beforeEach(() => {
    mockUseFilterTaxonomyQuery.mockReturnValue({ data: [] });
    mockUseGameDetailsQuery.mockReturnValue({ data: null });
    mockUseGamesQuery.mockReturnValue({
      data: { games: [], total: 0 },
      isLoading: false,
      error: null,
      isFetching: false,
    });
  });

  test('renders the browse shell and applies a filter', () => {
    renderGameList();

    fireEvent.click(screen.getByRole('button', { name: /Filters/ }));
    expect(screen.getByText('Filter Games')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '4' }));
    expect(mockUseGamesQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        playerOptions: expect.objectContaining({ count: 4 }),
      })
    );
  });

  test('restores a taxonomy selection from the URL', () => {
    mockUseFilterTaxonomyQuery.mockReturnValue({
      data: [
        {
          option_id: 'game-type:dice-games',
          label: 'Dice Games',
          group: 'game_type',
          featured: false,
          sources: [
            { type: 'category', id: 1017, name: 'Dice' },
            { type: 'mechanic', id: 2072, name: 'Dice Rolling' },
          ],
        },
      ],
    });

    renderGameList(['/?game_types=game-type:dice-games']);

    fireEvent.click(screen.getByRole('button', { name: /Filters/ }));
    fireEvent.click(screen.getByText('Game Type'));
    fireEvent.click(screen.getByRole('button', { name: 'Show All Game Types' }));
    expect(screen.getByRole('button', { name: 'Dice Games' })).toHaveAttribute('aria-pressed', 'true');
    expect(mockUseGamesQuery).toHaveBeenCalledWith(
      expect.objectContaining({ selectedGameTypeIds: ['game-type:dice-games'] })
    );
  });

  test('passes a detail classification into the filter state', async () => {
    const game = {
      id: 1,
      name: 'Test Game',
      min_players: 2,
      max_players: 4,
      min_playtime: 30,
      max_playtime: 60,
      average_weight: 2.5,
      average: 7.5,
    };
    mockUseGamesQuery.mockReturnValue({
      data: { games: [game], total: 1 },
      isLoading: false,
      error: null,
      isFetching: false,
    });
    mockUseGameDetailsQuery.mockReturnValue({ data: game });

    renderGameList();
    fireEvent.click(await screen.findByText('Test Game'));

    fireEvent.click(screen.getByRole('button', { name: 'Party Game detail' }));
    expect(screen.getByRole('button', { name: 'Party Game detail' })).toHaveAttribute('aria-pressed', 'true');
    expect(mockUseGamesQuery).toHaveBeenCalledWith(
      expect.objectContaining({ gameStyle: 'party' })
    );
  });
});
