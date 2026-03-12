const requestState = {
  lastGamesQuery: null,
  tokenRequests: 0,
  recommendationRequests: [],
};

export const resetMswState = () => {
  requestState.lastGamesQuery = null;
  requestState.tokenRequests = 0;
  requestState.recommendationRequests = [];
};

export const getMswState = () => requestState;
