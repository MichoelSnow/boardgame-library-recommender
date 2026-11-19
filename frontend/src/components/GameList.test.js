import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import {
  fireEvent,
  render,
  screen,
  waitForElementToBeRemoved,
} from '@testing-library/react';

import AuthContext from '../context/AuthContext';
import GameList from './GameList';
import { createTestQueryClient, withQueryClient } from '../test/testProviders';

const mockUseGamesQuery = jest.fn();

jest.mock('../hooks/useGameListQueries', () => ({
  useMechanicsQuery: () => ({ data: [] }),
  useCategoriesQuery: () => ({ data: [] }),
  useLibraryGameIdsQuery: () => ({ data: [] }),
  useCatalogStateQuery: () => ({ data: { state_token: 'token-1' } }),
  useGamesQuery: (params) => mockUseGamesQuery(params),
  useGameDetailsQuery: () => ({ data: null }),
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

const renderGameList = () =>
  render(
    withQueryClient(
      <MemoryRouter>
        <AuthContext.Provider value={{ user: { id: 1, username: 'admin' } }}>
          <GameList />
        </AuthContext.Provider>
      </MemoryRouter>,
      createTestQueryClient()
    )
  );

describe('GameList browse shell', () => {
  beforeEach(() => {
    mockUseGamesQuery.mockReturnValue({
      data: { games: [], total: 0 },
      isLoading: false,
      error: null,
      isFetching: false,
    });
  });

  test('opens search, clears the query, and closes search', () => {
    renderGameList();

    fireEvent.click(screen.getByLabelText('Open search'));
    const searchInput = screen.getByLabelText('Search Games');
    fireEvent.change(searchInput, { target: { value: 'Wingspan' } });
    fireEvent.click(screen.getByLabelText('Clear search'));
    expect(searchInput).toHaveValue('');

    fireEvent.click(screen.getByLabelText('Close search'));
    expect(screen.getByLabelText('Open search')).toBeInTheDocument();
  });

  test('selects an existing sort option', () => {
    renderGameList();

    fireEvent.click(screen.getByRole('button', { name: 'Sort' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Name (A-Z)' }));

    expect(mockUseGamesQuery).toHaveBeenCalledWith(
      expect.objectContaining({ sortBy: 'name_asc' })
    );
  });

  test('opens and closes the filter drawer', async () => {
    renderGameList();

    fireEvent.click(screen.getByRole('button', { name: /Filters/ }));
    expect(screen.getByText('Filter Games')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Close filters' }));
    await waitForElementToBeRemoved(() => screen.queryByText('Filter Games'));
  });
});
