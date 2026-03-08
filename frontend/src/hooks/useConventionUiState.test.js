import { act, renderHook } from '@testing-library/react';
import { useConventionUiState } from './useConventionUiState';

describe('useConventionUiState', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  test('kiosk mode shows non-library notification on every toggle-on', () => {
    const { result } = renderHook(() => useConventionUiState(true, true));

    act(() => {
      result.current.toggleAllBoardGames(true);
    });
    expect(result.current.showNonLibraryNotification).toBe(true);
    expect(result.current.paxOnly).toBe(false);

    act(() => {
      result.current.setShowNonLibraryNotification(false);
      result.current.toggleAllBoardGames(false);
      result.current.toggleAllBoardGames(true);
    });
    expect(result.current.showNonLibraryNotification).toBe(true);
  });

  test('non-kiosk mode shows non-library notification once per session', () => {
    const { result } = renderHook(() => useConventionUiState(true, false));

    act(() => {
      result.current.toggleAllBoardGames(true);
    });
    expect(result.current.showNonLibraryNotification).toBe(true);

    act(() => {
      result.current.setShowNonLibraryNotification(false);
      result.current.toggleAllBoardGames(false);
      result.current.toggleAllBoardGames(true);
    });
    expect(result.current.showNonLibraryNotification).toBe(false);
  });
});
