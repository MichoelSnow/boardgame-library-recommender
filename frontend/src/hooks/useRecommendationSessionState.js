import { useEffect, useMemo, useRef, useState } from 'react';

const RECOMMENDATION_STATE_STORAGE_PREFIX = 'game_list_recommendation_state_v1';
const RECOMMENDATION_STATE_TTL_MS = 60 * 60 * 1000;

const buildRecommendationStorageKey = (identity) =>
  `${RECOMMENDATION_STATE_STORAGE_PREFIX}:${identity || 'anonymous'}`;

const loadRecommendationState = (storageKey) => {
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw);
    if (!parsed?.savedAt || Date.now() - parsed.savedAt > RECOMMENDATION_STATE_TTL_MS) {
      window.sessionStorage.removeItem(storageKey);
      return null;
    }

    return parsed;
  } catch (_err) {
    window.sessionStorage.removeItem(storageKey);
    return null;
  }
};

const saveRecommendationState = (storageKey, state) => {
  try {
    window.sessionStorage.setItem(
      storageKey,
      JSON.stringify({
        ...state,
        savedAt: Date.now(),
      })
    );
  } catch (_err) {
    // Best-effort persistence only.
  }
};

const clearRecommendationState = (storageKey) => {
  try {
    window.sessionStorage.removeItem(storageKey);
  } catch (_err) {
    // No-op if storage is unavailable.
  }
};

export const useRecommendationSessionState = ({ user }) => {
  const [likedGames, setLikedGames] = useState([]);
  const [dislikedGames, setDislikedGames] = useState([]);
  const [hasRecommendations, setHasRecommendations] = useState(false);
  const [showingRecommendations, setShowingRecommendations] = useState(false);
  const [recommendationsStale, setRecommendationsStale] = useState(false);
  const [allRecommendations, setAllRecommendations] = useState([]);

  const userIdentity = useMemo(
    () => (user?.id != null ? String(user.id) : user?.username || null),
    [user]
  );
  const recommendationStorageKey = useMemo(
    () => buildRecommendationStorageKey(userIdentity),
    [userIdentity]
  );
  const hydratedRecommendationStorageKeyRef = useRef(null);
  const isHydratedRef = useRef(false);

  useEffect(() => {
    isHydratedRef.current = false;
  }, [recommendationStorageKey]);

  useEffect(() => {
    if (!userIdentity) {
      return;
    }
    if (hydratedRecommendationStorageKeyRef.current === recommendationStorageKey) {
      return;
    }
    hydratedRecommendationStorageKeyRef.current = recommendationStorageKey;

    const persistedState = loadRecommendationState(recommendationStorageKey);
    if (!persistedState) {
      isHydratedRef.current = true;
      return;
    }

    setLikedGames(Array.isArray(persistedState.likedGames) ? persistedState.likedGames : []);
    setDislikedGames(Array.isArray(persistedState.dislikedGames) ? persistedState.dislikedGames : []);
    setAllRecommendations(
      Array.isArray(persistedState.allRecommendations) ? persistedState.allRecommendations : []
    );
    setHasRecommendations(Boolean(persistedState.hasRecommendations));
    setShowingRecommendations(Boolean(persistedState.showingRecommendations));
    setRecommendationsStale(Boolean(persistedState.recommendationsStale));
    isHydratedRef.current = true;
  }, [recommendationStorageKey, userIdentity]);

  useEffect(() => {
    if (!userIdentity) {
      return;
    }
    if (!isHydratedRef.current) {
      return;
    }

    const hasPersistableState =
      likedGames.length > 0 ||
      dislikedGames.length > 0 ||
      allRecommendations.length > 0 ||
      hasRecommendations ||
      showingRecommendations ||
      recommendationsStale;

    if (!hasPersistableState) {
      clearRecommendationState(recommendationStorageKey);
      return;
    }

    saveRecommendationState(recommendationStorageKey, {
      likedGames,
      dislikedGames,
      allRecommendations,
      hasRecommendations,
      showingRecommendations,
      recommendationsStale,
    });
  }, [
    allRecommendations,
    dislikedGames,
    hasRecommendations,
    likedGames,
    recommendationStorageKey,
    recommendationsStale,
    showingRecommendations,
    userIdentity,
  ]);

  const likeGame = (game) => {
    setLikedGames((prev) => {
      const exists = prev.some((g) => g.id === game.id);
      return exists ? prev.filter((g) => g.id !== game.id) : [...prev, game];
    });
    setDislikedGames((prev) => prev.filter((g) => g.id !== game.id));
    if (hasRecommendations) {
      setRecommendationsStale(true);
    }
  };

  const dislikeGame = (game) => {
    setDislikedGames((prev) => {
      const exists = prev.some((g) => g.id === game.id);
      return exists ? prev.filter((g) => g.id !== game.id) : [...prev, game];
    });
    setLikedGames((prev) => prev.filter((g) => g.id !== game.id));
    if (hasRecommendations) {
      setRecommendationsStale(true);
    }
  };

  const resetRecommendationState = () => {
    setLikedGames([]);
    setDislikedGames([]);
    setHasRecommendations(false);
    setShowingRecommendations(false);
    setRecommendationsStale(false);
    setAllRecommendations([]);
  };

  return {
    likedGames,
    dislikedGames,
    hasRecommendations,
    showingRecommendations,
    recommendationsStale,
    allRecommendations,
    setLikedGames,
    setDislikedGames,
    setHasRecommendations,
    setShowingRecommendations,
    setRecommendationsStale,
    setAllRecommendations,
    likeGame,
    dislikeGame,
    resetRecommendationState,
  };
};
