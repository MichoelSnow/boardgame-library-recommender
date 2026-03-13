import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

import { useGamesQuery } from '../hooks/useGameListQueries';
import { getMswState } from '../test/msw/state';
import { withQueryClient } from '../test/testProviders';

const GamesQueryHarness = ({ searchTerm = 'alpha' }) => {
  const { data, error, isLoading } = useGamesQuery({
    gamesPerPage: 24,
    currentPage: 2,
    sortBy: 'rank',
    libraryOnly: true,
    searchTerm,
    playerOptions: { count: 4, recommendation: 'recommended' },
    selectedDesigners: [{ boardgamedesigner_id: 12, boardgamedesigner_name: 'D' }],
    selectedArtists: [{ boardgameartist_id: 21, boardgameartist_name: 'A' }],
    selectedMechanicIds: [1, 2],
    selectedCategoryIds: [7, 8],
    weight: { beginner: true, midweight: false, heavy: true },
    isRecommendation: false,
  });

  if (isLoading) {
    return <div>loading</div>;
  }
  if (error) {
    return <div>error-state</div>;
  }
  return <div>games-total:{data.total}</div>;
};

describe('games filtering integration', () => {
  test('sends expected query params for filtering/pagination/sort', async () => {
    render(withQueryClient(<GamesQueryHarness />));

    await screen.findByText('games-total:1');

    const query = getMswState().lastGamesQuery;
    expect(query).toContain('limit=24');
    expect(query).toContain('skip=24');
    expect(query).toContain('sort_by=rank');
    expect(query).toContain('library_only=true');
    expect(query).toContain('search=alpha');
    expect(query).toContain('players=4');
    expect(query).toContain('recommendations=recommended');
    expect(query).toContain('designer_id=12');
    expect(query).toContain('artist_id=21');
    expect(query).toContain('mechanics=1%2C2');
    expect(query).toContain('categories=7%2C8');
    expect(query).toContain('weight=beginner%2Cheavy');
  });

  test('exposes API error state when games API fails', async () => {
    render(withQueryClient(<GamesQueryHarness searchTerm="trigger-error" />));

    await waitFor(() => {
      expect(screen.getByText('error-state')).toBeInTheDocument();
    });
  });
});
