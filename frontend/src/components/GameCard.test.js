import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import GameCard from './GameCard';

const baseGame = {
  id: 1,
  name: 'Test Game',
  min_players: 1,
  max_players: 4,
  min_playtime: 30,
  max_playtime: 60,
  average_weight: 2.5,
  average: 7.1,
  year_published: 2020,
  rank: 100,
};

const noop = () => {};

describe('GameCard image fallback behavior', () => {
  test('uses placeholder image immediately when game image URL is missing', () => {
    render(
      <GameCard
        game={{ ...baseGame, image: null }}
        onClick={noop}
        sortBy="rank"
        onLike={noop}
        onDislike={noop}
      />
    );

    const image = screen.getByAltText('Test Game');
    expect(image.getAttribute('src')).toContain('/assets/images/game-placeholder.svg');
  });

  test('falls back to placeholder after all image candidates fail', async () => {
    render(
      <GameCard
        game={{
          ...baseGame,
          image: 'https://cf.geekdo-images.com/example/original/img/test-image.jpg',
        }}
        onClick={noop}
        sortBy="rank"
        onLike={noop}
        onDislike={noop}
      />
    );

    const image = screen.getByAltText('Test Game');
    fireEvent.error(image);
    fireEvent.error(image);
    fireEvent.error(image);
    fireEvent.error(image);

    await waitFor(() => {
      expect(image.getAttribute('src')).toContain('/assets/images/game-placeholder.svg');
    });
  });
});
