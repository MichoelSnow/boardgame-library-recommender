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

  test('migrates filters into persistent accordion sections', async () => {
    renderGameList();

    fireEvent.click(screen.getByRole('button', { name: /Filters/ }));
    expect(screen.getByText('Filter Games')).toBeInTheDocument();
    expect(screen.getByText('Group & Requirements')).toBeInTheDocument();
    expect(screen.getByText('Players')).toBeInTheDocument();
    expect(screen.getByText('Complexity')).toBeInTheDocument();
    expect(screen.getByText('Game Type')).toBeInTheDocument();
    expect(screen.getByText('Theme & Setting')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '4' }));
    expect(mockUseGamesQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        playerOptions: expect.objectContaining({ count: 4 }),
      })
    );

    fireEvent.click(screen.getByRole('button', { name: 'Close filters' }));
    await waitForElementToBeRemoved(() => screen.queryByText('Filter Games'));

    fireEvent.click(screen.getByRole('button', { name: /Filters \(1\)/ }));
    expect(screen.getByRole('button', { name: '4' })).toHaveAttribute('aria-pressed', 'true');
  });

  test('Clear All only clears filter constraints', () => {
    renderGameList(['/?search=Wingspan&sort=name_asc&library_only=false&players=4&weight=beginner']);

    fireEvent.click(screen.getByRole('button', { name: /Filters \(2\)/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Clear All' }));

    expect(mockUseGamesQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        searchTerm: 'Wingspan',
        sortBy: 'name_asc',
        libraryOnly: false,
        playerOptions: expect.objectContaining({ count: null }),
        weight: { beginner: false, midweight: false, heavy: false },
      })
    );
    expect(screen.getByLabelText('Search Games')).toHaveValue('Wingspan');
  });
});
