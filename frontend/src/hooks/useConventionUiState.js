import { useState } from 'react';

const NON_LIBRARY_NOTICE_SESSION_KEY = 'hasSeenNonLibraryMessage';

export const useConventionUiState = (initialPaxOnly, isConventionKiosk) => {
  const [paxOnly, setPaxOnly] = useState(initialPaxOnly);
  const [showNonLibraryNotification, setShowNonLibraryNotification] = useState(false);
  const [hasSeenNonLibraryMessage, setHasSeenNonLibraryMessage] = useState(
    window.sessionStorage.getItem(NON_LIBRARY_NOTICE_SESSION_KEY) === 'true'
  );

  const toggleAllBoardGames = (showAllBoardGames) => {
    setPaxOnly(!showAllBoardGames);
    setShowNonLibraryNotification(false);

    if (showAllBoardGames) {
      if (isConventionKiosk) {
        setShowNonLibraryNotification(true);
        return;
      }

      if (!hasSeenNonLibraryMessage) {
        setShowNonLibraryNotification(true);
        setHasSeenNonLibraryMessage(true);
        window.sessionStorage.setItem(NON_LIBRARY_NOTICE_SESSION_KEY, 'true');
      }
    }
  };

  return {
    paxOnly,
    setPaxOnly,
    showNonLibraryNotification,
    setShowNonLibraryNotification,
    toggleAllBoardGames,
  };
};
