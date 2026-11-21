import React from 'react';
import { render, screen } from '@testing-library/react';

import { useGamesQuery } from '../hooks/useGameListQueries';
import { getMswState } from '../test/msw/state';
import { withQueryClient } from '../test/testProviders';

const GamesQueryHarness = () => {
  const { data, isLoading } = useGamesQuery({
    gamesPerPage: 24,
    currentPage: 2,
    sortBy: 'rank',
    libraryOnly: false,
    searchTerm: 'alpha',
    playerOptions: { count: 4 },
    selectedDesigners: [],
    selectedArtists: [],
    selectedMechanicIds: [],
    selectedCategoryIds: [],
    selectedGameTypeIds: ['game-type:dice-games'],
    selectedThemeIds: ['theme:fantasy'],
    weight: { beginner: false, midweight: false, heavy: false },
    gameStyle: 'party',
    cooperative: true,
    isRecommendation: false,
  });

  if (isLoading || !data) {
    return <div>loading</div>;
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
    expect(query).toContain('search=alpha');
    expect(query).toContain('players=4');
    expect(query).toContain('game_types=game-type%3Adice-games');
    expect(query).toContain('themes=theme%3Afantasy');
    expect(query).toContain('game_style=party');
    expect(query).toContain('cooperative=true');
  });
});
