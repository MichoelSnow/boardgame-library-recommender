import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import GameDetails from './GameDetails';

jest.mock('../hooks/useGameListQueries', () => ({
  useGameRecommendationsQuery: jest.fn(),
}));

jest.mock('./GameCard', () => {
  return function MockGameCard({ game }) {
    return <div>{game.name}</div>;
  };
});

const { useGameRecommendationsQuery } = require('../hooks/useGameListQueries');

const baseGame = {
  id: 1,
  name: 'Base Game',
  description: 'Desc',
  min_players: 2,
  max_players: 4,
  mechanics: [],
  categories: [],
  designers: [],
  artists: [],
  publishers: [],
  suggested_players: [],
};

const defaultProps = {
  game: baseGame,
  open: true,
  onClose: jest.fn(),
  onFilter: jest.fn(),
  likedGames: [],
  dislikedGames: [],
  onLike: jest.fn(),
  onDislike: jest.fn(),
};

describe('GameDetails recommendations integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders loading state while recommendations query is pending', () => {
    useGameRecommendationsQuery.mockReturnValue({
      data: null,
      isLoading: true,
      isError: false,
    });

    render(<GameDetails {...defaultProps} />);

    expect(screen.getByRole('progressbar')).toBeTruthy();
  });

  test('renders recommendation cards from query data', () => {
    useGameRecommendationsQuery.mockReturnValue({
      data: {
        data: [{ id: 2, name: 'Recommended A' }],
        headers: {},
      },
      isLoading: false,
      isError: false,
    });

    render(<GameDetails {...defaultProps} />);

    expect(screen.getByText('Recommended A')).toBeTruthy();
  });

  test('renders recommendation error state on query failure', () => {
    useGameRecommendationsQuery.mockReturnValue({
      data: null,
      isLoading: false,
      isError: true,
    });

    render(<GameDetails {...defaultProps} />);

    expect(screen.getByText('Unable to load similar games right now.')).toBeTruthy();
  });

  test('keeps dialog open when applying a mechanic filter from details', () => {
    useGameRecommendationsQuery.mockReturnValue({
      data: { data: [], headers: {} },
      isLoading: false,
      isError: false,
    });

    const onClose = jest.fn();
    const onFilter = jest.fn();
    const gameWithMechanic = {
      ...baseGame,
      mechanics: [{ boardgamemechanic_id: 7, boardgamemechanic_name: 'Deck Building' }],
    };

    render(
      <GameDetails
        {...defaultProps}
        game={gameWithMechanic}
        onClose={onClose}
        onFilter={onFilter}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Deck Building' }));

    expect(onFilter).toHaveBeenCalledWith('mechanic', 7, 'Deck Building');
    expect(onClose).not.toHaveBeenCalled();
  });

  test('shows in-library indicator in dialog header when game is in library', () => {
    useGameRecommendationsQuery.mockReturnValue({
      data: { data: [], headers: {} },
      isLoading: false,
      isError: false,
    });

    render(
      <GameDetails
        {...defaultProps}
        isLibraryGame={true}
        game={{ ...baseGame, avg_box_volume: 80 }}
      />
    );

    expect(screen.getByLabelText('Available in Library Library')).toBeTruthy();
  });

  test('uses primary color for selected filter chips and removes it when deselected', () => {
    useGameRecommendationsQuery.mockReturnValue({
      data: { data: [], headers: {} },
      isLoading: false,
      isError: false,
    });

    const gameWithMechanic = {
      ...baseGame,
      mechanics: [{ boardgamemechanic_id: 7, boardgamemechanic_name: 'Deck Building' }],
    };

    const { rerender } = render(
      <GameDetails
        {...defaultProps}
        game={gameWithMechanic}
        selectedMechanicIds={[7]}
      />
    );

    const filterChip = screen.getByRole('button', { name: 'Deck Building' });
    expect(filterChip).toHaveClass('MuiChip-colorPrimary');
    expect(filterChip).not.toHaveClass('MuiChip-outlined');

    rerender(
      <GameDetails
        {...defaultProps}
        game={gameWithMechanic}
        selectedMechanicIds={[]}
      />
    );

    const deselectedFilterChip = screen.getByRole('button', { name: 'Deck Building' });
    expect(deselectedFilterChip).not.toHaveClass('MuiChip-colorPrimary');
    expect(deselectedFilterChip).toHaveClass('MuiChip-outlined');
  });

  test('shows best and recommended player counts when suggested player data is present', () => {
    useGameRecommendationsQuery.mockReturnValue({
      data: { data: [], headers: {} },
      isLoading: false,
      isError: false,
    });

    const gameWithSuggestedPlayers = {
      ...baseGame,
      suggested_players: [
        { player_count: 3, recommendation_level: 'recommended', best: 2, recommended: 8, not_recommended: 1 },
        { player_count: 4, recommendation_level: 'best', best: 9, recommended: 3, not_recommended: 1 },
      ],
    };

    render(<GameDetails {...defaultProps} game={gameWithSuggestedPlayers} />);

    expect(screen.getByText('Best: 4')).toBeTruthy();
    expect(screen.getByText('Rec: 3')).toBeTruthy();
  });
});
