import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "https://bg-lib-app-dev.fly.dev";
const THINK_TIME_SECONDS = Number(__ENV.THINK_TIME_SECONDS || "0.3");
const RECOMMENDATION_LIMIT = Number(__ENV.RECOMMENDATION_LIMIT || "5");
const LIBRARY_ONLY = (__ENV.LIBRARY_ONLY || "true").toLowerCase() === "true";
const GAME_IDS = (__ENV.GAME_IDS || "224517,167791,174430,173346,266192,161936,13,822,30549,68448")
  .split(",")
  .map((value) => Number(value.trim()))
  .filter((value) => Number.isInteger(value) && value > 0);
const LIKED_MIN = Math.max(1, Number(__ENV.LIKED_MIN || "1"));
const LIKED_MAX = Math.max(LIKED_MIN, Number(__ENV.LIKED_MAX || "50"));
const WEIGHT_API = Number(__ENV.WEIGHT_API || "0.40");
const WEIGHT_VERSION = Number(__ENV.WEIGHT_VERSION || "0.20");
const WEIGHT_RECOMMENDATIONS = Number(__ENV.WEIGHT_RECOMMENDATIONS || "0.25");
const WEIGHT_GAMES = Number(__ENV.WEIGHT_GAMES || "0.15");

const VUS = Number(__ENV.VUS || "20");
const DURATION = __ENV.DURATION || "5m";

const recommendationDuration = new Trend("recommendation_duration");
const recommendationDurationByLikedSize = new Trend("recommendation_duration_by_liked_size");
const gamesDuration = new Trend("games_duration");
const recommendationErrorRate = new Rate("recommendation_error_rate");
const gamesErrorRate = new Rate("games_error_rate");

export const options = {
  vus: VUS,
  duration: DURATION,
  thresholds: {
    http_req_failed: ["rate<0.02"],
    http_req_duration: ["p(95)<2500"],
    recommendation_duration: ["p(95)<4000"],
    recommendation_error_rate: ["rate<0.02"],
    games_duration: ["p(95)<2500"],
    games_error_rate: ["rate<0.02"],
  },
};

const totalWeight =
  WEIGHT_API + WEIGHT_VERSION + WEIGHT_RECOMMENDATIONS + WEIGHT_GAMES;
if (totalWeight <= 0) {
  throw new Error("At least one route weight must be > 0.");
}
const routeBoundaryApi = WEIGHT_API / totalWeight;
const routeBoundaryVersion = (WEIGHT_API + WEIGHT_VERSION) / totalWeight;
const routeBoundaryRecommendations =
  (WEIGHT_API + WEIGHT_VERSION + WEIGHT_RECOMMENDATIONS) / totalWeight;

function pickLikedSizeBucket(count) {
  if (count <= 5) {
    return "01_05";
  }
  if (count <= 10) {
    return "06_10";
  }
  if (count <= 20) {
    return "11_20";
  }
  if (count <= 35) {
    return "21_35";
  }
  return "36_50";
}

function requestApiRoot() {
  const response = http.get(`${BASE_URL}/api`);
  check(response, {
    "GET /api status is 200": (r) => r.status === 200,
  });
}

function requestVersion() {
  const response = http.get(`${BASE_URL}/api/version`);
  check(response, {
    "GET /api/version status is 200": (r) => r.status === 200,
  });
}

function requestRecommendations() {
  const maxCount = Math.min(LIKED_MAX, GAME_IDS.length);
  if (maxCount < 1) {
    recommendationErrorRate.add(true);
    return;
  }

  const minCount = Math.min(LIKED_MIN, maxCount);
  const selectedCount = Math.floor(Math.random() * (maxCount - minCount + 1)) + minCount;
  const likedGames = [...GAME_IDS]
    .sort(() => Math.random() - 0.5)
    .slice(0, selectedCount);

  const payload = JSON.stringify({
    liked_games: likedGames,
    limit: RECOMMENDATION_LIMIT,
    library_only: LIBRARY_ONLY,
  });

  const response = http.post(`${BASE_URL}/api/recommendations`, payload, {
    headers: { "Content-Type": "application/json" },
  });
  recommendationDuration.add(response.timings.duration);
  recommendationDurationByLikedSize.add(response.timings.duration, {
    liked_size_bucket: pickLikedSizeBucket(selectedCount),
  });
  recommendationErrorRate.add(response.status !== 200);
  check(response, {
    "POST /api/recommendations status is 200": (r) => r.status === 200,
  });
}

function requestGamesList() {
  const response = http.get(
    `${BASE_URL}/api/games/?skip=0&limit=20&sort_by=rank&library_only=true`
  );
  gamesDuration.add(response.timings.duration);
  gamesErrorRate.add(response.status !== 200);
  check(response, {
    "GET /api/games status is 200": (r) => r.status === 200,
  });
}

export default function () {
  const route = Math.random();
  if (route < routeBoundaryApi) {
    requestApiRoot();
  } else if (route < routeBoundaryVersion) {
    requestVersion();
  } else if (route < routeBoundaryRecommendations) {
    requestRecommendations();
  } else {
    requestGamesList();
  }

  sleep(THINK_TIME_SECONDS);
}
