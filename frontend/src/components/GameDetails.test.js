import React from 'react';
import { render, screen } from '@testing-library/react';
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
  mechanics: [],
  categories: [],
  designers: [],
  artists: [],
  publishers: [],
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
});
