import React, {
  useState,
  useEffect,
  memo,
  useContext,
  useCallback,
  useRef,
} from 'react';
import {
  Container,
  Grid,
  Card,
  CardContent,
  Typography,
  TextField,
  Box,
  Alert,
  Button,
  FormControlLabel,
  CircularProgress,
  Chip,
  Skeleton,
  Pagination,
  InputAdornment,
  Stack,
  Switch,
  Tooltip,
  IconButton,
} from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import SearchIcon from '@mui/icons-material/Search';
import PeopleIcon from '@mui/icons-material/People';
import PsychologyAltOutlinedIcon from '@mui/icons-material/PsychologyAltOutlined';
import SortIcon from '@mui/icons-material/Sort';
import GameDetails from './GameDetails';
import GameCard from './GameCard';
import ConstructionIcon from '@mui/icons-material/Construction';
import CategoryIcon from '@mui/icons-material/Category';
import CloseIcon from '@mui/icons-material/Close';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import LikedGamesDialog from './LikedGamesDialog';
import AuthContext from '../context/AuthContext';
import poweredByBggLogo from '../assets/powered-by-bgg.svg';
import { useQueryClient } from '@tanstack/react-query';
import { useConventionUiState } from '../hooks/useConventionUiState';
import {
  useCatalogStateQuery,
  useCategoriesQuery,
  useConventionKioskStatusQuery,
  useGameDetailsQuery,
  useGamesQuery,
  useMechanicsQuery,
  useLibraryGameIdsQuery,
} from '../hooks/useGameListQueries';
import { useRecommendationMutation } from '../hooks/useRecommendationMutation';
import { useRecommendationSessionState } from '../hooks/useRecommendationSessionState';

// Helper function to decode HTML entities and preserve line breaks
// const decodeHtmlEntities = (text) => {
//   if (!text) return '';
//   const textarea = document.createElement('textarea');
//   textarea.innerHTML = text;
//   return textarea.value
//     .replace(/<br\s*\/?>/gi, '\n')
//     .replace(/&#10;/g, '\n')
//     .replace(/&#13;/g, '\n')
//     .replace(/&nbsp;/g, ' ');
// };

// Sort options for the game list
const sortOptions = [
  { value: 'rank', label: 'Overall Rank' },
  { value: 'abstracts_rank', label: 'Abstract Games' },
  { value: 'cgs_rank', label: 'Customizable Games' },
  { value: 'childrens_games_rank', label: "Children's Games" },
  { value: 'family_games_rank', label: 'Family Games' },
  { value: 'party_games_rank', label: 'Party Games' },
  { value: 'strategy_games_rank', label: 'Strategy Games' },
  { value: 'thematic_rank', label: 'Thematic Games' },
  { value: 'wargames_rank', label: 'Wargames' },
  { value: 'name_asc', label: 'Name (A-Z)' },
  { value: 'name_desc', label: 'Name (Z-A)' }
];

// Helper function to get rank label
// const getRankLabel = (sortValue) => {
//   const option = sortOptions.find(opt => opt.value === sortValue);
//   return option ? option.label : 'Rank';
// };

// Generate player count options (1-12)
const playerCountOptions = Array.from({ length: 12 }, (_, i) => i + 1);

const VALID_PLAYER_RECOMMENDATIONS = new Set(['allowed', 'recommended', 'best']);
const VALID_SORT_OPTIONS = new Set(sortOptions.map((option) => option.value));

const parseIntegerParam = (value) => {
  if (!value) {
    return null;
  }

  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
};

const parseBooleanParam = (value, fallback) => {
  if (value === 'true') {
    return true;
  }
  if (value === 'false') {
    return false;
  }
  return fallback;
};

const parseCsvIntegers = (value) => {
  if (!value) {
    return [];
  }

  return value
    .split(',')
    .map((item) => Number.parseInt(item, 10))
    .filter((item) => !Number.isNaN(item));
};

const buildPlaceholderSelection = (ids, idKey, nameKey) =>
  ids.map((id) => ({
    [idKey]: id,
    [nameKey]: '',
  }));

// Memoized GameCardSkeleton component
const GameCardSkeleton = memo(() => (
  <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
    <Skeleton variant="rectangular" height={140} />
    <CardContent sx={{ flexGrow: 1, p: 1.5 }}>
      <Skeleton variant="text" width="80%" height={24} sx={{ mb: 0.5 }} />
      <Skeleton variant="text" width="60%" height={20} sx={{ mb: 0.5 }} />
      <Skeleton variant="text" width="40%" height={20} />
    </CardContent>
  </Card>
));

const GameList = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSearchValue = searchParams.get('search') || '';
  const initialPlayerCount = parseIntegerParam(searchParams.get('players'));
  const initialPlayerRecommendation = searchParams.get('player_rec');
  const initialWeightValues = new Set(
    (searchParams.get('weight') || '')
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
  );
  const initialMechanicIds = parseCsvIntegers(searchParams.get('mechanics'));
  const initialCategoryIds = parseCsvIntegers(searchParams.get('categories'));
  const initialSortBy = searchParams.get('sort');
  const initialLibraryOnly = parseBooleanParam(searchParams.get('library_only'), true);

  const [inputValue, setInputValue] = useState(initialSearchValue);
  const [searchTerm, setSearchTerm] = useState(initialSearchValue);
  const [playerOptions, setPlayerOptions] = useState({
    count: initialPlayerCount,
    recommendation: VALID_PLAYER_RECOMMENDATIONS.has(initialPlayerRecommendation)
      ? initialPlayerRecommendation
      : 'allowed',
  });
  const [weight, setWeight] = useState({
    beginner: initialWeightValues.has('beginner'),
    midweight: initialWeightValues.has('midweight'),
    heavy: initialWeightValues.has('heavy')
  });
  const [selectedDesigners, setSelectedDesigners] = useState([]);
  const [selectedArtists, setSelectedArtists] = useState([]);
  const [selectedMechanics, setSelectedMechanics] = useState(
    buildPlaceholderSelection(
      initialMechanicIds,
      'boardgamemechanic_id',
      'boardgamemechanic_name'
    )
  );
  const [selectedCategories, setSelectedCategories] = useState(
    buildPlaceholderSelection(
      initialCategoryIds,
      'boardgamecategory_id',
      'boardgamecategory_name'
    )
  );
  const [selectedGameId, setSelectedGameId] = useState(null);
  const [selectedGamePreview, setSelectedGamePreview] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [sortBy, setSortBy] = useState(
    VALID_SORT_OPTIONS.has(initialSortBy) ? initialSortBy : 'rank'
  );
  const [currentPage, setCurrentPage] = useState(1);
  const gamesPerPage = 24;
  const [activeFilter, setActiveFilter] = useState(null);

  const { user } = useContext(AuthContext);
  const queryClient = useQueryClient();

  const [isLikedGamesDialogOpen, setIsLikedGamesDialogOpen] = useState(false);
  const [gameList, setGameList] = useState([]);
  const [totalGames, setTotalGames] = useState(0);
  const [isRecommendation, setIsRecommendation] = useState(false);
  const [recommendationNotice, setRecommendationNotice] = useState(null);
  const lastCatalogStateTokenRef = useRef(null);
  const { data: kioskStatus } = useConventionKioskStatusQuery();
  const { data: catalogState } = useCatalogStateQuery();
  const isConventionKiosk = Boolean(kioskStatus?.kiosk_mode);
  const {
    libraryOnly,
    setLibraryOnly,
    showNonLibraryNotification,
    setShowNonLibraryNotification,
    toggleAllBoardGames,
  } = useConventionUiState(initialLibraryOnly, isConventionKiosk);
  const {
    likedGames,
    dislikedGames,
    hasRecommendations,
    showingRecommendations,
    recommendationsStale,
    allRecommendations,
    setHasRecommendations,
    setShowingRecommendations,
    setRecommendationsStale,
    setAllRecommendations,
    likeGame,
    dislikeGame,
    resetRecommendationState,
  } = useRecommendationSessionState({ user });
  const selectedMechanicIds = selectedMechanics.map(
    (item) => item.boardgamemechanic_id
  );
  const selectedCategoryIds = selectedCategories.map(
    (item) => item.boardgamecategory_id
  );
  const recommendationMutation = useRecommendationMutation();
  const isRecommendationLoading = recommendationMutation.isPending;

  const { data: popularMechanics = [] } = useMechanicsQuery();
  const { data: popularCategories = [] } = useCategoriesQuery();
  const { data: libraryGameIds = [] } = useLibraryGameIdsQuery();

  const {
    data: response = { games: [], total: 0 },
    isLoading,
    error,
  } = useGamesQuery({
    gamesPerPage,
    currentPage,
    sortBy,
    libraryOnly,
    searchTerm,
    playerOptions,
    selectedDesigners,
    selectedArtists,
    selectedMechanicIds,
    selectedCategoryIds,
    weight,
    isRecommendation,
  });

  const { data: selectedGame } = useGameDetailsQuery({
    gameId: selectedGameId,
    enabled: detailsOpen,
  });

  const refreshCatalogData = useCallback(
    async ({ includeFilters = true } = {}) => {
      const querySpecs = [
        { queryKey: ['games'], type: 'active' },
        { queryKey: ['library_game_ids'], type: 'active' },
      ];
      if (includeFilters) {
        querySpecs.push(
          { queryKey: ['mechanics_alphabetically'], type: 'active' },
          { queryKey: ['categories_alphabetically'], type: 'active' }
        );
      }
      await Promise.all(querySpecs.map((querySpec) => queryClient.refetchQueries(querySpec)));
    },
    [queryClient]
  );

  const handleRecommend = async () => {
    try {
      setRecommendationNotice(null);
      const fallbackGames = response?.games || [];
      const fallbackTotal = response?.total || 0;
      const allResponse = await recommendationMutation.mutateAsync({
        likedGames: likedGames.map((g) => g.id),
        dislikedGames: dislikedGames.map((g) => g.id),
        limit: 50, // Backend currently caps recommendation requests at 50
        libraryOnly: false,
        recommenderMode: 'hybrid',
      });
      const recommendationsAvailable =
        allResponse.headers['x-recommendations-available'] !== 'false';

      if (!recommendationsAvailable) {
        setAllRecommendations([]);
        setGameList(fallbackGames);
        setTotalGames(fallbackTotal);
        setHasRecommendations(false);
        setShowingRecommendations(false);
        setIsRecommendation(false);
        setRecommendationNotice({
          severity: 'warning',
          message:
            'Recommendations are temporarily unavailable while recommendation artifacts are missing or invalid. The rest of the app is still available.',
        });
        return;
      }

      if (allResponse.data.length === 0) {
        setAllRecommendations([]);
        setGameList(fallbackGames);
        setTotalGames(fallbackTotal);
        setHasRecommendations(false);
        setShowingRecommendations(false);
        setIsRecommendation(false);
        setRecommendationNotice({
          severity: 'info',
          message:
            'No recommendations matched your current liked and disliked games. Try adjusting your selections.',
        });
        return;
      }

      setAllRecommendations(allResponse.data);
      setCurrentPage(1);
      setIsRecommendation(true);
      setSortBy('recommendation_score');
      setActiveFilter(null);
      
      // Update new recommendation states
      setHasRecommendations(true);
      setShowingRecommendations(true);
      setRecommendationsStale(false);
    } catch (err) {
      setRecommendationNotice({
        severity: 'error',
        message: 'Unable to generate recommendations right now.',
      });
      console.error('Failed to fetch recommendations:', err);
    }
  };

  const handleToggleFilter = (filter) => {
    setActiveFilter(prev => (prev === filter ? null : filter));
  };

  const handleResetFilters = () => {
    setInputValue('');
    setSearchTerm('');
    setPlayerOptions({ count: null, recommendation: 'allowed' });
    setWeight({ beginner: false, midweight: false, heavy: false });
    setSelectedMechanics([]);
    setSelectedCategories([]);
    setSelectedDesigners([]);
    setSelectedArtists([]);
    setSortBy('rank');
    setActiveFilter(null);
    setCurrentPage(1);
    setIsRecommendation(false);
    setLibraryOnly(true);
    
    // Reset recommendation states
    resetRecommendationState();
    setRecommendationNotice(null);
  };

  const handleClearAll = () => {
    const hasRecommendationState =
      hasRecommendations ||
      allRecommendations.length > 0 ||
      likedGames.length > 0 ||
      dislikedGames.length > 0;

    if (hasRecommendationState) {
      const confirmed = window.confirm(
        'Clear All will also remove liked/disliked games and reset recommendations. Continue?'
      );
      if (!confirmed) {
        return;
      }
    }

    handleResetFilters();
  };

  const handlePlayerCountChange = (event, newCount) => {
    setPlayerOptions(prev => ({
      ...prev,
      count: newCount,
    }));
  };

  const handlePlayerRecChange = (event, newRec) => {
    if (newRec !== null) {
      setPlayerOptions(prev => ({ ...prev, recommendation: newRec }));
    }
  };

  // Handle search input change
  const handleSearchChange = (event) => {
    setInputValue(event.target.value);
  };

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setSearchTerm(inputValue);
    }, 500);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [inputValue]);

  // Keep the current view state in the URL so refresh preserves search, sorting, and filters.
  useEffect(() => {
    const nextSearchParams = new URLSearchParams(searchParams);

    if (searchTerm) {
      nextSearchParams.set('search', searchTerm);
    } else {
      nextSearchParams.delete('search');
    }

    if (sortBy !== 'rank') {
      nextSearchParams.set('sort', sortBy);
    } else {
      nextSearchParams.delete('sort');
    }

    nextSearchParams.set('library_only', String(libraryOnly));

    if (playerOptions.count) {
      nextSearchParams.set('players', String(playerOptions.count));
      if (playerOptions.recommendation !== 'allowed') {
        nextSearchParams.set('player_rec', playerOptions.recommendation);
      } else {
        nextSearchParams.delete('player_rec');
      }
    } else {
      nextSearchParams.delete('players');
      nextSearchParams.delete('player_rec');
    }

    const activeWeights = Object.entries(weight)
      .filter(([, checked]) => checked)
      .map(([key]) => key);
    if (activeWeights.length > 0) {
      nextSearchParams.set('weight', activeWeights.join(','));
    } else {
      nextSearchParams.delete('weight');
    }

    if (selectedMechanicIds.length > 0) {
      nextSearchParams.set('mechanics', selectedMechanicIds.join(','));
    } else {
      nextSearchParams.delete('mechanics');
    }

    if (selectedCategoryIds.length > 0) {
      nextSearchParams.set('categories', selectedCategoryIds.join(','));
    } else {
      nextSearchParams.delete('categories');
    }

    nextSearchParams.delete('page');

    if (nextSearchParams.toString() === searchParams.toString()) {
      return;
    }
    setSearchParams(nextSearchParams, { replace: true });
  }, [
    libraryOnly,
    playerOptions,
    searchParams,
    searchTerm,
    selectedCategoryIds,
    selectedCategories,
    selectedMechanicIds,
    selectedMechanics,
    setSearchParams,
    sortBy,
    weight,
  ]);

  useEffect(() => {
    if (!popularMechanics.length || !selectedMechanics.length) {
      return;
    }

    const mechanicsById = new Map(
      popularMechanics.map((item) => [item.boardgamemechanic_id, item])
    );

    setSelectedMechanics((previous) => {
      let changed = false;
      const next = previous.map((item) => {
        const resolved = mechanicsById.get(item.boardgamemechanic_id);
        if (resolved && resolved.boardgamemechanic_name !== item.boardgamemechanic_name) {
          changed = true;
          return resolved;
        }
        return item;
      });

      return changed ? next : previous;
    });
  }, [popularMechanics, selectedMechanics.length]);

  useEffect(() => {
    if (!popularCategories.length || !selectedCategories.length) {
      return;
    }

    const categoriesById = new Map(
      popularCategories.map((item) => [item.boardgamecategory_id, item])
    );

    setSelectedCategories((previous) => {
      let changed = false;
      const next = previous.map((item) => {
        const resolved = categoriesById.get(item.boardgamecategory_id);
        if (resolved && resolved.boardgamecategory_name !== item.boardgamecategory_name) {
          changed = true;
          return resolved;
        }
        return item;
      });

      return changed ? next : previous;
    });
  }, [popularCategories, selectedCategories.length]);

  useEffect(() => {
    if (!isRecommendation && response?.games) {
      setGameList(response.games);
      setTotalGames(response.total);
    }
  }, [response, isRecommendation]);

  useEffect(() => {
    const token = catalogState?.state_token;
    if (!token) {
      return;
    }
    if (lastCatalogStateTokenRef.current === null) {
      lastCatalogStateTokenRef.current = token;
      return;
    }
    if (lastCatalogStateTokenRef.current !== token) {
      lastCatalogStateTokenRef.current = token;
      refreshCatalogData({ includeFilters: false });
    }
  }, [catalogState?.state_token, refreshCatalogData]);

  useEffect(() => {
    if (showingRecommendations && hasRecommendations) {
      let newGameList = allRecommendations;
      if (libraryOnly && libraryGameIds.length > 0) {
        const librarySet = new Set(libraryGameIds);
        newGameList = allRecommendations.filter(game => librarySet.has(game.id));
      }
      setGameList(newGameList);
      setTotalGames(newGameList.length);
      setCurrentPage(1);
      setIsRecommendation(true);
    } else {
      setIsRecommendation(false);
    }
  }, [showingRecommendations, hasRecommendations, libraryOnly, allRecommendations, libraryGameIds]);

  const isSortFiltered = sortBy !== 'rank';
  const sortButtonLabel = isSortFiltered ? (sortOptions.find(opt => opt.value === sortBy)?.label || 'Sort') : 'Sort';

  const isPlayersFiltered = playerOptions.count !== null;
  const playerButtonLabel = (() => {
    if (!isPlayersFiltered) return 'Players';
    let label = `${playerOptions.count}`;
    if (playerOptions.count === playerCountOptions.length) label += '+';
    label += ` Player${playerOptions.count > 1 ? 's' : ''}`;
    if (playerOptions.recommendation && playerOptions.recommendation !== 'allowed') {
      label += ` (${playerOptions.recommendation.charAt(0).toUpperCase() + playerOptions.recommendation.slice(1)})`;
    }
    return label;
  })();

  const activeWeightLabels = Object.entries(weight)
    .filter(([, checked]) => checked)
    .map(([key]) => {
      if (key === 'beginner') return 'Beginner';
      if (key === 'midweight') return 'Midweight';
      if (key === 'heavy') return 'Heavy';
      return '';
    });
  const isWeightFiltered = activeWeightLabels.length > 0;
  const weightButtonLabel = isWeightFiltered ? activeWeightLabels.join(', ') : 'Weight';

  const isMechanicsFiltered = selectedMechanics.length > 0;
  const mechanicsButtonLabel = isMechanicsFiltered ? selectedMechanics.map(m => m.boardgamemechanic_name).join(', ') : 'Mechanics';

  const isCategoriesFiltered = selectedCategories.length > 0;
  const categoriesButtonLabel = isCategoriesFiltered ? selectedCategories.map(c => c.boardgamecategory_name).join(', ') : 'Categories';

  const clearSortFilter = () => {
    setSortBy('rank');
    if (activeFilter === 'sort') {
      setActiveFilter(null);
    }
  };

  const clearPlayersFilter = () => {
    setPlayerOptions({ count: null, recommendation: 'allowed' });
    if (activeFilter === 'players') {
      setActiveFilter(null);
    }
  };

  const clearWeightFilter = () => {
    setWeight({ beginner: false, midweight: false, heavy: false });
    if (activeFilter === 'weight') {
      setActiveFilter(null);
    }
  };

  const clearMechanicsFilter = () => {
    setSelectedMechanics([]);
    if (activeFilter === 'mechanics') {
      setActiveFilter(null);
    }
  };

  const clearCategoriesFilter = () => {
    setSelectedCategories([]);
    if (activeFilter === 'categories') {
      setActiveFilter(null);
    }
  };

  const renderFilterButton = ({
    label,
    variant,
    onToggle,
    startIcon,
    disabled,
    showClear = false,
    onClear,
    clearAriaLabel,
    dataTour,
  }) => (
    <Box sx={{ position: 'relative', display: 'inline-flex' }}>
      <Button
        variant={variant}
        onClick={onToggle}
        startIcon={startIcon}
        disabled={disabled}
        sx={{
          textTransform: 'none',
          pr: showClear ? 3 : undefined,
        }}
        data-tour={dataTour}
      >
        {label}
      </Button>
      {showClear && onClear && (
        <IconButton
          aria-label={clearAriaLabel}
          size="small"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onClear();
          }}
          onMouseDown={(event) => {
            event.stopPropagation();
          }}
          disabled={disabled}
          sx={{
            position: 'absolute',
            top: 0,
            right: 0,
            transform: 'translate(40%, -40%)',
            p: 0.2,
            zIndex: 1,
            color: '#000000',
            backgroundColor: '#ffffff',
            border: (theme) => `1px solid ${theme.palette.secondary.main}`,
            '&:hover': {
              backgroundColor: '#ffffff',
            },
          }}
        >
          <CloseIcon sx={{ fontSize: '0.85rem' }} />
        </IconButton>
      )}
    </Box>
  );

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, playerOptions, selectedDesigners, selectedArtists, selectedMechanics, selectedCategories, weight, sortBy]);

  const handlePageChange = (event, newPage) => {
    setCurrentPage(newPage);
  };

  const handleGameClick = (game) => {
    setSelectedGameId(game.id);
    setSelectedGamePreview(game);
    setDetailsOpen(true);
  };

  const handleFilter = (type, id, name) => {
    if (type === 'game') {
      handleGameClick({ id });
    } else if (type === 'designer') {
      setSelectedDesigners(prev => {
        const exists = prev.some(d => d.boardgamedesigner_id === id);
        if (exists) {
          return prev.filter(d => d.boardgamedesigner_id !== id);
        } else {
          return [...prev, { boardgamedesigner_id: id, boardgamedesigner_name: name }];
        }
      });
    } else if (type === 'artist') {
      setSelectedArtists(prev => {
        const exists = prev.some(a => a.boardgameartist_id === id);
        if (exists) {
          return prev.filter(a => a.boardgameartist_id !== id);
        } else {
          return [...prev, { boardgameartist_id: id, boardgameartist_name: name }];
        }
      });
    } else if (type === 'mechanic') {
      setSelectedMechanics(prev => {
        const exists = prev.some(m => m.boardgamemechanic_id === id);
        if (exists) {
          return prev.filter(m => m.boardgamemechanic_id !== id);
        } else {
          return [...prev, { boardgamemechanic_id: id, boardgamemechanic_name: name }];
        }
      });
    } else if (type === 'category') {
      setSelectedCategories(prev => {
        const exists = prev.some(c => c.boardgamecategory_id === id);
        if (exists) {
          return prev.filter(c => c.boardgamecategory_id !== id);
        } else {
          return [...prev, { boardgamecategory_id: id, boardgamecategory_name: name }];
        }
      });
    }
  };

  const handleRemoveFilter = (type, id) => {
    if (type === 'designer') {
      setSelectedDesigners(prev => prev.filter(d => d.boardgamedesigner_id !== id));
    } else if (type === 'artist') {
      setSelectedArtists(prev => prev.filter(a => a.boardgameartist_id !== id));
    } else if (type === 'mechanic') {
      setSelectedMechanics(prev => prev.filter(m => m.boardgamemechanic_id !== id));
    } else if (type === 'category') {
      setSelectedCategories(prev => prev.filter(c => c.boardgamecategory_id !== id));
    }
  };

  const renderFilterChips = () => {
    const chips = [];
    
    selectedDesigners.forEach(designer => {
      chips.push(
        <Chip
          key={`designer-${designer.boardgamedesigner_id}`}
          label={`Designer: ${designer.boardgamedesigner_name}`}
          onDelete={() => handleRemoveFilter('designer', designer.boardgamedesigner_id)}
          color="primary"
          sx={{ m: 0.5 }}
        />
      );
    });
    
    selectedArtists.forEach(artist => {
      chips.push(
        <Chip
          key={`artist-${artist.boardgameartist_id}`}
          label={`Artist: ${artist.boardgameartist_name}`}
          onDelete={() => handleRemoveFilter('artist', artist.boardgameartist_id)}
          color="primary"
          sx={{ m: 0.5 }}
        />
      );
    });

    return chips.length > 0 ? (
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
        {chips}
      </Box>
    ) : null;
  };

  const renderGameGrid = () => {
    if (isLoading) {
      return (
        <Grid container spacing={3}>
          {Array.from(new Array(gamesPerPage)).map((_, index) => (
            <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={index}>
              <GameCardSkeleton />
            </Grid>
          ))}
        </Grid>
      );
    }

    if (error) {
      return (
        <Alert severity="error" sx={{ mt: 2 }}>
          Failed to load games: {error.message}
        </Alert>
      );
    }

    if (gameList.length === 0) {
      return (
        <Box sx={{ textAlign: 'center', mt: 4 }}>
          <Typography variant="h6">No games found</Typography>
          <Typography color="text.secondary">Try adjusting your filters or search term.</Typography>
        </Box>
      );
    }

    const listToRender = isRecommendation
      ? gameList.slice((currentPage - 1) * gamesPerPage, currentPage * gamesPerPage)
      : gameList;

    return (
      <Grid container spacing={3}>
        {listToRender.map((game) => (
          <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={game.id}>
            <GameCard 
              game={game} 
              onClick={() => handleGameClick(game)} 
              sortBy={isRecommendation ? 'recommendation_score' : sortBy}
              liked={likedGames.some(g => g.id === game.id)}
              disliked={dislikedGames.some(g => g.id === game.id)}
              onLike={() => likeGame(game)}
              onDislike={() => dislikeGame(game)}
              isLibraryGame={libraryGameIds.includes(game.id)}
            />
          </Grid>
        ))}
      </Grid>
    );
  };

  return (
    <>
      <Container maxWidth="xl" sx={{ py: 3 }}>
        <Stack spacing={2} sx={{ mb: 2 }}>
          {/* Search Input */}
          <Tooltip 
            title={isRecommendation ? "Search is disabled in recommendation mode. Untoggle 'Show Recommendations' to enable search." : "Search games by name"}
            placement="top"
          >
            <TextField
              label="Search Games"
              variant="outlined"
              value={inputValue}
              onChange={handleSearchChange}
              disabled={isRecommendation}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
                endAdornment: inputValue ? (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label="Clear search"
                      edge="end"
                      size="small"
                      onClick={() => {
                        setInputValue('');
                        setSearchTerm('');
                      }}
                    >
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ) : null,
              }}
            />
          </Tooltip>

          {/* Filter Bar */}
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ flexWrap: 'wrap', gap: 1 }}>
            <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ gap: 1 }}>
              <Tooltip title="Show non-library games for recommendations and information">
                <FormControlLabel
                  control={<Switch checked={!libraryOnly} onChange={(e) => {
                    const showNonLibrary = e.target.checked;
                    toggleAllBoardGames(showNonLibrary);
                    setCurrentPage(1);
                  }} />}
                  label="All Board Games"
                  sx={{ mr: 2 }}
                  data-tour="library-toggle"
                />
              </Tooltip>
              {renderFilterButton({
                label: sortButtonLabel,
                variant: isSortFiltered || activeFilter === 'sort' ? 'contained' : 'outlined',
                onToggle: () => handleToggleFilter('sort'),
                startIcon: <SortIcon />,
                disabled: isRecommendation,
                showClear: isSortFiltered,
                onClear: clearSortFilter,
                clearAriaLabel: 'Clear sort filter',
              })}
              {renderFilterButton({
                label: playerButtonLabel,
                variant: isPlayersFiltered || activeFilter === 'players' ? 'contained' : 'outlined',
                onToggle: () => handleToggleFilter('players'),
                startIcon: <PeopleIcon />,
                disabled: isRecommendation,
                showClear: isPlayersFiltered,
                onClear: clearPlayersFilter,
                clearAriaLabel: 'Clear players filter',
                dataTour: 'player-filter',
              })}
              {renderFilterButton({
                label: weightButtonLabel,
                variant: isWeightFiltered || activeFilter === 'weight' ? 'contained' : 'outlined',
                onToggle: () => handleToggleFilter('weight'),
                startIcon: <PsychologyAltOutlinedIcon />,
                disabled: isRecommendation,
                showClear: isWeightFiltered,
                onClear: clearWeightFilter,
                clearAriaLabel: 'Clear weight filter',
              })}
              {renderFilterButton({
                label: mechanicsButtonLabel,
                variant: isMechanicsFiltered || activeFilter === 'mechanics' ? 'contained' : 'outlined',
                onToggle: () => handleToggleFilter('mechanics'),
                startIcon: <ConstructionIcon />,
                disabled: isRecommendation,
                showClear: isMechanicsFiltered,
                onClear: clearMechanicsFilter,
                clearAriaLabel: 'Clear mechanics filter',
              })}
              {renderFilterButton({
                label: categoriesButtonLabel,
                variant: isCategoriesFiltered || activeFilter === 'categories' ? 'contained' : 'outlined',
                onToggle: () => handleToggleFilter('categories'),
                startIcon: <CategoryIcon />,
                disabled: isRecommendation,
                showClear: isCategoriesFiltered,
                onClear: clearCategoriesFilter,
                clearAriaLabel: 'Clear categories filter',
              })}
            </Stack>
            <Stack direction="row" spacing={1}>
              <Button onClick={handleClearAll} size="small">
                Clear All
              </Button>
            </Stack>
          </Stack>
          
          {/* Active Filter Panel */}
          {activeFilter && (
            <>
              {activeFilter === 'sort' && (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {isRecommendation && (
                    <Button
                      variant={sortBy === 'recommendation_score' ? 'contained' : 'outlined'}
                      onClick={() => setSortBy('recommendation_score')}
                      size="small"
                    >
                      Relevance
                    </Button>
                  )}
                  {sortOptions.map(option => (
                    <Button
                      key={option.value}
                      variant={sortBy === option.value ? 'contained' : 'outlined'}
                      onClick={() => setSortBy(option.value)}
                      size="small"
                    >
                      {option.label}
                    </Button>
                  ))}
                </Box>
              )}
              {activeFilter === 'players' && (
                <Stack spacing={1} sx={{ gap: 1 }}>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    <Button
                      variant={playerOptions.count === null ? 'contained' : 'outlined'}
                      onClick={() => handlePlayerCountChange(null, null)}
                      size="small"
                    >
                      Any
                    </Button>
                    {playerCountOptions.map(count => (
                      <Button
                        key={count}
                        variant={playerOptions.count === count ? 'contained' : 'outlined'}
                        onClick={() => handlePlayerCountChange(null, count)}
                        size="small"
                      >
                        {count}
                      </Button>
                    ))}
                  </Box>
                  {playerOptions.count && (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      <Button size="small" variant={playerOptions.recommendation === 'allowed' ? 'contained' : 'outlined'} onClick={() => handlePlayerRecChange(null, 'allowed')}>Allowed</Button>
                      <Button size="small" variant={playerOptions.recommendation === 'recommended' ? 'contained' : 'outlined'} onClick={() => handlePlayerRecChange(null, 'recommended')}>Recommended</Button>
                      <Button size="small" variant={playerOptions.recommendation === 'best' ? 'contained' : 'outlined'} onClick={() => handlePlayerRecChange(null, 'best')}>Best</Button>
                    </Box>
                  )}
                </Stack>
              )}
              {activeFilter === 'weight' && (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  <Button size="small" variant={weight.beginner ? 'contained' : 'outlined'} onClick={() => setWeight(w => ({ ...w, beginner: !w.beginner }))}>Beginner Friendly (≤ 2.0)</Button>
                  <Button size="small" variant={weight.midweight ? 'contained' : 'outlined'} onClick={() => setWeight(w => ({ ...w, midweight: !w.midweight }))}>Midweight (2.0 - 4.0)</Button>
                  <Button size="small" variant={weight.heavy ? 'contained' : 'outlined'} onClick={() => setWeight(w => ({ ...w, heavy: !w.heavy }))}>Heavy (≥ 4.0)</Button>
                </Box>
              )}
              {activeFilter === 'mechanics' && (
                <Box sx={{ maxHeight: '400px', overflow: 'auto', pb: 1 }}>
                  <Grid container spacing={1}>
                    {popularMechanics.map(mech => (
                      <Grid size={{ xs: 6, sm: 4, md: 3 }} key={mech.boardgamemechanic_id}>
                        <Button
                          fullWidth
                          variant={selectedMechanics.some(m => m.boardgamemechanic_id === mech.boardgamemechanic_id) ? 'contained' : 'outlined'}
                          onClick={() => {
                            const isSelected = selectedMechanics.some(m => m.boardgamemechanic_id === mech.boardgamemechanic_id);
                            if (isSelected) {
                              setSelectedMechanics(selectedMechanics.filter(m => m.boardgamemechanic_id !== mech.boardgamemechanic_id));
                            } else {
                              setSelectedMechanics([...selectedMechanics, mech]);
                            }
                          }}
                          size="small"
                          sx={{ 
                            textAlign: 'center', 
                            height: '100%',
                            display: 'flex',
                            justifyContent: 'center',
                            fontSize: '0.8rem',
                            lineHeight: 1.2,
                            p: 1
                          }}
                        >
                          {mech.boardgamemechanic_name}
                        </Button>
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              )}
              {activeFilter === 'categories' && (
                <Box sx={{ maxHeight: '400px', overflow: 'auto', pb: 1 }}>
                  <Grid container spacing={1}>
                    {popularCategories.map(cat => (
                      <Grid size={{ xs: 6, sm: 4, md: 3 }} key={cat.boardgamecategory_id}>
                        <Button
                          fullWidth
                          variant={selectedCategories.some(c => c.boardgamecategory_id === cat.boardgamecategory_id) ? 'contained' : 'outlined'}
                          onClick={() => {
                            const isSelected = selectedCategories.some(c => c.boardgamecategory_id === cat.boardgamecategory_id);
                            if (isSelected) {
                              setSelectedCategories(selectedCategories.filter(c => c.boardgamecategory_id !== cat.boardgamecategory_id));
                            } else {
                              setSelectedCategories([...selectedCategories, cat]);
                            }
                          }}
                          size="small"
                          sx={{ 
                            textAlign: 'center', 
                            height: '100%',
                            display: 'flex',
                            justifyContent: 'center',
                            fontSize: '0.8rem',
                            lineHeight: 1.2,
                            p: 1
                          }}
                        >
                          {cat.boardgamecategory_name}
                        </Button>
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              )}
            </>
          )}

          {/* Action Buttons and Filter Chips */}
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
              {hasRecommendations ? (
                <Tooltip title={recommendationsStale ? "Generate new recommendations based on your updated preferences" : "Recommendations are up to date with your current preferences"}>
                  <span>
                    <Button 
                      variant="contained" 
                      onClick={handleRecommend}
                      disabled={!recommendationsStale || isRecommendationLoading}
                      data-tour="refresh-recommendations-button"
                    >
                      Refresh Recommendations
                    </Button>
                  </span>
                </Tooltip>
              ) : (
                <Tooltip title={user ? "Get recommendations based on your liked/disliked games. Need at least 1 liked or disliked game." : "You must be logged in to get recommendations"}>
                  <span>
                    <Button
                      onClick={handleRecommend}
                      variant="contained"
                      color="primary"
                      disabled={!user || (likedGames.length === 0 && dislikedGames.length === 0) || isRecommendationLoading}
                      data-tour="recommend-button"
                    >
                      Recommend Games
                    </Button>
                  </span>
                </Tooltip>
              )}
              <Tooltip title="View your liked/disliked games">
                <Button
                    onClick={() => setIsLikedGamesDialogOpen(true)}
                    size="small"
                >
                    Liked/Disliked ({likedGames.length}/{dislikedGames.length})
                </Button>
              </Tooltip>
              {hasRecommendations && (
                <Tooltip title="Toggle between showing only recommended games or the full game library">
                  <FormControlLabel
                    control={
                      <Switch 
                        checked={showingRecommendations} 
                        onChange={(e) => {
                          const nextChecked = e.target.checked;
                          if (nextChecked) {
                            setActiveFilter(null);
                          }
                          setShowingRecommendations(nextChecked);
                        }}
                        data-tour="show-recommendations-toggle"
                      />
                    }
                    label="Show Recommendations"
                    sx={{ ml: 1 }}
                  />
                </Tooltip>
              )}
              {renderFilterChips()}
          </Box>
        </Stack>

        {isRecommendationLoading && (
          <Box sx={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', bgcolor: 'rgba(255,255,255,0.6)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Stack spacing={2} alignItems="center">
              <CircularProgress size={64} />
              <Typography variant="h6">Generating recommendations...</Typography>
            </Stack>
          </Box>
        )}

        {showNonLibraryNotification && (
          <Alert 
            severity="info" 
            onClose={() => setShowNonLibraryNotification(false)}
            sx={{ mb: 2 }}
          >
            We are showing you non-library games for recommendation and informational purposes only. 
            Any game without a <MenuBookIcon sx={{ fontSize: '1rem', verticalAlign: 'middle', mx: 0.25 }} /> icon is not in the library.
          </Alert>
        )}

        {recommendationNotice && (
          <Alert
            severity={recommendationNotice.severity}
            onClose={() => setRecommendationNotice(null)}
            sx={{ mb: 2 }}
          >
            {recommendationNotice.message}
          </Alert>
        )}

        {renderGameGrid()}

        <Box sx={{ mt: 4 }}>
          <Box
            sx={{
              display: { xs: 'flex', md: 'grid' },
              flexDirection: { xs: 'column', md: 'row' },
              gridTemplateColumns: { md: '1fr auto 1fr' },
              alignItems: 'center',
              gap: 2,
            }}
          >
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 2,
                gridColumn: { md: 2 },
                width: { xs: '100%', md: 'auto' },
              }}
            >
            <Typography variant="body2" color="text.secondary">
              {isRecommendation
                ? `${totalGames.toLocaleString()} recommendation${totalGames !== 1 ? 's' : ''}`
                : `${totalGames.toLocaleString()} game${totalGames !== 1 ? 's' : ''} found`}
            </Typography>
            <Pagination
              count={Math.ceil(totalGames / gamesPerPage)}
              page={currentPage}
              onChange={handlePageChange}
              color="primary"
              showFirstButton
              showLastButton
            />
            </Box>
            <Box
              sx={{
                width: { xs: '100%', md: 'auto' },
                display: 'flex',
                justifyContent: 'flex-end',
                gridColumn: { md: 3 },
              }}
            >
              <a
                className="powered-by-bgg-badge"
                href="https://boardgamegeek.com/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Powered by BoardGameGeek"
              >
                <img src={poweredByBggLogo} alt="Powered by BGG" />
              </a>
            </Box>
          </Box>
        </Box>

        {detailsOpen && (selectedGame || selectedGamePreview) && (
          <GameDetails
            game={selectedGame || selectedGamePreview}
            open={detailsOpen}
            onClose={() => {
              setDetailsOpen(false);
              setSelectedGameId(null);
              setSelectedGamePreview(null);
            }}
            onLike={likeGame}
            onDislike={dislikeGame}
            likedGames={likedGames}
            dislikedGames={dislikedGames}
            onFilter={handleFilter}
            isLibraryGame={libraryGameIds.includes((selectedGame || selectedGamePreview).id)}
            selectedDesignerIds={selectedDesigners.map((designer) => designer.boardgamedesigner_id)}
            selectedArtistIds={selectedArtists.map((artist) => artist.boardgameartist_id)}
            selectedMechanicIds={selectedMechanicIds}
            selectedCategoryIds={selectedCategoryIds}
            libraryGameIds={libraryGameIds}
          />
        )}
      </Container>
      <LikedGamesDialog
        open={isLikedGamesDialogOpen}
        onClose={() => setIsLikedGamesDialogOpen(false)}
        likedGames={likedGames}
        dislikedGames={dislikedGames}
        onRemoveLike={likeGame}
        onRemoveDislike={dislikeGame}
      />
    </>
  );
};

export default memo(GameList); 
