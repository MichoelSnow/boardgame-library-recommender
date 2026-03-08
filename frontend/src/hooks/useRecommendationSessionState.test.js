import { act, renderHook } from '@testing-library/react';
import { useRecommendationSessionState } from './useRecommendationSessionState';

describe('useRecommendationSessionState', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  test('persists and hydrates recommendation state for the same user session', () => {
    const user = { id: 7, username: 'tester' };
    const sampleGame = { id: 42, name: 'Game A' };

    const { result, unmount } = renderHook(({ activeUser }) =>
      useRecommendationSessionState({ user: activeUser }), {
      initialProps: { activeUser: user },
    });

    act(() => {
      result.current.likeGame(sampleGame);
      result.current.setHasRecommendations(true);
      result.current.setShowingRecommendations(true);
      result.current.setAllRecommendations([{ id: 99, recommendation_score: 0.9 }]);
    });

    unmount();

    const { result: hydrated } = renderHook(() =>
      useRecommendationSessionState({ user })
    );

    expect(hydrated.current.likedGames).toEqual([sampleGame]);
    expect(hydrated.current.hasRecommendations).toBe(true);
    expect(hydrated.current.showingRecommendations).toBe(true);
    expect(hydrated.current.allRecommendations).toEqual([
      { id: 99, recommendation_score: 0.9 },
    ]);
  });
});
