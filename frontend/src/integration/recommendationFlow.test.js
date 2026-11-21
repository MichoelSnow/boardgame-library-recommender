import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { useRecommendationMutation } from '../hooks/useRecommendationMutation';
import { getMswState } from '../test/msw/state';
import { withQueryClient } from '../test/testProviders';

const RecommendationHarness = () => {
  const mutation = useRecommendationMutation();

  const onClick = () => {
    mutation.mutate({
      likedGames: [1, 2],
      dislikedGames: [4],
      limit: 50,
      libraryOnly: true,
    });
  };

  return (
    <div>
      <button type="button" onClick={onClick}>
        fetch
      </button>
      {mutation.isPending && <div>loading</div>}
      {mutation.isSuccess && (
        <div>recommendation-count:{mutation.data.data.length}</div>
      )}
    </div>
  );
};

describe('recommendation flow integration', () => {
  test('submits recommendation payload and returns results', async () => {
    render(withQueryClient(<RecommendationHarness />));

    await userEvent.click(screen.getByRole('button', { name: 'fetch' }));

    await screen.findByText('recommendation-count:2');
    expect(getMswState().recommendationRequests).toHaveLength(1);
    expect(getMswState().recommendationRequests[0]).toEqual({
      liked_games: [1, 2],
      disliked_games: [4],
      limit: 50,
      library_only: true,
    });
  });

});
