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
  Drawer,
  Divider,
  Popover,
  MenuItem,
  MenuList,
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
const FILTER_DRAWER_HISTORY_KEY = '__gameListFilterDrawer';

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

const BrowseHeader = ({
  searchOpen,
  inputValue,
  isRecommendation,
  onSearchChange,
  onClearSearch,
  onCloseSearch,
  onOpenSearch,
}) => (
  <Box
    component="header"
    sx={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      minHeight: 56,
      gap: 1,
    }}
  >
    <Typography variant="h6" component="h1" noWrap>
      PAX Game Library
    </Typography>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
      {searchOpen ? (
        <TextField
          autoFocus
          size="small"
          label="Search Games"
          value={inputValue}
          onChange={onSearchChange}
          disabled={isRecommendation}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              onCloseSearch();
            }
          }}
          InputProps={{
            startAdornment: <InputAdornment position="start"><SearchIcon /></InputAdornment>,
            endAdornment: (
              <InputAdornment position="end">
                {inputValue && (
                  <IconButton aria-label="Clear search" size="small" onClick={onClearSearch}>
                    <CloseIcon fontSize="small" />
                  </IconButton>
                )}
                <IconButton aria-label="Close search" size="small" onClick={onCloseSearch}>
                  <CloseIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
      ) : (
        <Tooltip title={isRecommendation ? 'Search is disabled in recommendation mode' : 'Search games'}>
          <span>
            <IconButton aria-label="Open search" onClick={onOpenSearch} disabled={isRecommendation}>
              <SearchIcon />
            </IconButton>
          </span>
        </Tooltip>
      )}
    </Box>
  </Box>
);

const BrowseToolbar = ({
  isRecommendation,
  sortBy,
  sortButtonLabel,
  sortMenuAnchorEl,
  activeFilterCount,
  libraryOnly,
  onOpenSort,
  onCloseSort,
  onSelectSort,
  onOpenFilters,
  onToggleLibrary,
}) => (
  <>
    <Stack direction="row" spacing={1} alignItems="center" sx={{ flexWrap: 'wrap', gap: 1 }}>
      <Button
        variant="contained"
        startIcon={<SortIcon />}
        onClick={onOpenSort}
        disabled={isRecommendation}
        aria-haspopup="menu"
        aria-expanded={Boolean(sortMenuAnchorEl)}
      >
        {sortButtonLabel}
      </Button>
      <Button
        variant="outlined"
        startIcon={<PeopleIcon />}
        onClick={onOpenFilters}
        disabled={isRecommendation}
        data-tour="player-filter"
      >
        Filters{activeFilterCount ? ` (${activeFilterCount})` : ''}
      </Button>
      <Tooltip title="Show non-library games for recommendations and information">
        <FormControlLabel
          control={<Switch checked={!libraryOnly} onChange={onToggleLibrary} />}
          label="All Board Games"
          sx={{ ml: 'auto', mr: 0 }}
          data-tour="library-toggle"
        />
      </Tooltip>
    </Stack>

    <Popover
      open={Boolean(sortMenuAnchorEl)}
      anchorEl={sortMenuAnchorEl}
      onClose={onCloseSort}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
    >
      <MenuList aria-label="Sort games">
        {sortOptions.map((option) => (
          <MenuItem key={option.value} selected={sortBy === option.value} onClick={() => onSelectSort(option.value)}>
            {option.label}
          </MenuItem>
        ))}
      </MenuList>
    </Popover>
  </>
);

const FilterDrawer = ({
  open,
  onClose,
  onClearAll,
  isRecommendation,
  isPlayersFiltered,
  isWeightFiltered,
  isMechanicsFiltered,
  isCategoriesFiltered,
  onToggleFilter,
  activeFilter,
  sortBy,
  onSortChange,
  playerOptions,
  onPlayerCountChange,
  onPlayerRecChange,
  weight,
  onWeightToggle,
  popularMechanics,
  selectedMechanics,
  onMechanicToggle,
  popularCategories,
  selectedCategories,
  onCategoryToggle,
}) => (
  <Drawer
    anchor="left"
    open={open}
    onClose={onClose}
    PaperProps={{ sx: { width: { xs: '90vw', sm: 420 }, maxWidth: '100vw' } }}
  >
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2 }}>
      <Typography variant="h6">Filter Games</Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Button onClick={onClearAll} size="small">Clear All</Button>
        <IconButton aria-label="Close filters" onClick={onClose}><CloseIcon /></IconButton>
      </Box>
    </Box>
    <Divider />
    <Box sx={{ p: 2, overflowY: 'auto', flex: 1 }}>
      <Stack spacing={1.5}>
        <Button fullWidth variant={isPlayersFiltered ? 'contained' : 'outlined'} startIcon={<PeopleIcon />} onClick={() => onToggleFilter('players')} disabled={isRecommendation}>Players</Button>
        <Button fullWidth variant={isWeightFiltered ? 'contained' : 'outlined'} startIcon={<PsychologyAltOutlinedIcon />} onClick={() => onToggleFilter('weight')} disabled={isRecommendation}>Weight</Button>
        <Button fullWidth variant={isMechanicsFiltered ? 'contained' : 'outlined'} startIcon={<ConstructionIcon />} onClick={() => onToggleFilter('mechanics')} disabled={isRecommendation}>Mechanics</Button>
        <Button fullWidth variant={isCategoriesFiltered ? 'contained' : 'outlined'} startIcon={<CategoryIcon />} onClick={() => onToggleFilter('categories')} disabled={isRecommendation}>Categories</Button>
      </Stack>
      {activeFilter && (
        <>
          {activeFilter === 'sort' && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {isRecommendation && (
                <Button
                  variant={sortBy === 'recommendation_score' ? 'contained' : 'outlined'}
                  onClick={() => onSortChange('recommendation_score')}
                  size="small"
                >
                  Relevance
                </Button>
              )}
              {sortOptions.map(option => (
                <Button
                  key={option.value}
                  variant={sortBy === option.value ? 'contained' : 'outlined'}
                  onClick={() => onSortChange(option.value)}
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
                  onClick={() => onPlayerCountChange(null, null)}
                  size="small"
                >
                  Any
                </Button>
                {playerCountOptions.map(count => (
                  <Button
                    key={count}
                    variant={playerOptions.count === count ? 'contained' : 'outlined'}
                    onClick={() => onPlayerCountChange(null, count)}
                    size="small"
                  >
                    {count}
                  </Button>
                ))}
              </Box>
              {playerOptions.count && (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  <Button size="small" variant={playerOptions.recommendation === 'allowed' ? 'contained' : 'outlined'} onClick={() => onPlayerRecChange(null, 'allowed')}>Allowed</Button>
                  <Button size="small" variant={playerOptions.recommendation === 'recommended' ? 'contained' : 'outlined'} onClick={() => onPlayerRecChange(null, 'recommended')}>Recommended</Button>
                  <Button size="small" variant={playerOptions.recommendation === 'best' ? 'contained' : 'outlined'} onClick={() => onPlayerRecChange(null, 'best')}>Best</Button>
                </Box>
              )}
            </Stack>
          )}
          {activeFilter === 'weight' && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              <Button size="small" variant={weight.beginner ? 'contained' : 'outlined'} onClick={() => onWeightToggle('beginner')}>Beginner Friendly (≤ 2.0)</Button>
              <Button size="small" variant={weight.midweight ? 'contained' : 'outlined'} onClick={() => onWeightToggle('midweight')}>Midweight (2.0 - 4.0)</Button>
              <Button size="small" variant={weight.heavy ? 'contained' : 'outlined'} onClick={() => onWeightToggle('heavy')}>Heavy (≥ 4.0)</Button>
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
                      onClick={() => onMechanicToggle(mech)}
                      size="small"
                      sx={{
                        textAlign: 'center',
                        height: '100%',
                        display: 'flex',
                        justifyContent: 'center',
                        fontSize: '0.8rem',
                        lineHeight: 1.2,
                        p: 1,
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
                      onClick={() => onCategoryToggle(cat)}
                      size="small"
                      sx={{
                        textAlign: 'center',
                        height: '100%',
                        display: 'flex',
                        justifyContent: 'center',
                        fontSize: '0.8rem',
                        lineHeight: 1.2,
                        p: 1,
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
    </Box>
  </Drawer>
);

const ActiveFilterChips = ({ selectedDesigners, selectedArtists, onRemove }) => {
  const chips = [
    ...selectedDesigners.map((designer) => ({
      key: `designer-${designer.boardgamedesigner_id}`,
      label: `Designer: ${designer.boardgamedesigner_name}`,
      type: 'designer',
      id: designer.boardgamedesigner_id,
    })),
    ...selectedArtists.map((artist) => ({
      key: `artist-${artist.boardgameartist_id}`,
      label: `Artist: ${artist.boardgameartist_name}`,
      type: 'artist',
      id: artist.boardgameartist_id,
    })),
  ];

  if (chips.length === 0) {
    return null;
  }

  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
      {chips.map((chip) => (
        <Chip
          key={chip.key}
          label={chip.label}
          onDelete={() => onRemove(chip.type, chip.id)}
          color="primary"
          sx={{ m: 0.5 }}
        />
      ))}
    </Box>
  );
};

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
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(Boolean(initialSearchValue));
  const [sortMenuAnchorEl, setSortMenuAnchorEl] = useState(null);

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

  const handleWeightToggle = (weightKey) => {
    setWeight((previous) => ({ ...previous, [weightKey]: !previous[weightKey] }));
  };

  const handleMechanicToggle = (mechanic) => {
    setSelectedMechanics((previous) => {
      const isSelected = previous.some(
        (item) => item.boardgamemechanic_id === mechanic.boardgamemechanic_id
      );
      return isSelected
        ? previous.filter((item) => item.boardgamemechanic_id !== mechanic.boardgamemechanic_id)
        : [...previous, mechanic];
    });
  };

  const handleCategoryToggle = (category) => {
    setSelectedCategories((previous) => {
      const isSelected = previous.some(
        (item) => item.boardgamecategory_id === category.boardgamecategory_id
      );
      return isSelected
        ? previous.filter((item) => item.boardgamecategory_id !== category.boardgamecategory_id)
        : [...previous, category];
    });
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
  const isWeightFiltered = Object.values(weight).some(Boolean);

  const isMechanicsFiltered = selectedMechanics.length > 0;
  const isCategoriesFiltered = selectedCategories.length > 0;
  const activeFilterCount =
    (isPlayersFiltered ? 1 : 0) +
    Object.values(weight).filter(Boolean).length +
    selectedMechanics.length +
    selectedCategories.length +
    selectedDesigners.length +
    selectedArtists.length;

  const closeSearch = () => {
    setInputValue('');
    setSearchTerm('');
    setSearchOpen(false);
  };

  const openSortMenu = (event) => {
    if (!isRecommendation) {
      setSortMenuAnchorEl(event.currentTarget);
    }
  };

  const closeSortMenu = () => setSortMenuAnchorEl(null);

  const selectSort = (value) => {
    setSortBy(value);
    closeSortMenu();
  };

  const openFilterDrawer = () => {
    if (filterDrawerOpen) {
      return;
    }

    window.history.pushState(
      { ...(window.history.state || {}), [FILTER_DRAWER_HISTORY_KEY]: true },
      '',
      `${window.location.pathname}${window.location.search}${window.location.hash}`
    );
    setFilterDrawerOpen(true);
  };

  const closeFilterDrawer = () => {
    if (!filterDrawerOpen) {
      return;
    }

    setFilterDrawerOpen(false);
    if (window.history.state?.[FILTER_DRAWER_HISTORY_KEY]) {
      window.history.back();
    }
  };

  useEffect(() => {
    const handlePopState = () => {
      setFilterDrawerOpen(false);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, playerOptions, selectedDesigners, selectedArtists, selectedMechanics, selectedCategories, weight, sortBy]);

  const handlePageChange = (event, newPage) => {
    setCurrentPage(newPage);
    window.scrollTo(0, 0);
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
          <BrowseHeader
            searchOpen={searchOpen}
            inputValue={inputValue}
            isRecommendation={isRecommendation}
            onSearchChange={handleSearchChange}
            onClearSearch={() => { setInputValue(''); setSearchTerm(''); }}
            onCloseSearch={closeSearch}
            onOpenSearch={() => setSearchOpen(true)}
          />

          <BrowseToolbar
            isRecommendation={isRecommendation}
            sortBy={sortBy}
            sortButtonLabel={sortButtonLabel}
            sortMenuAnchorEl={sortMenuAnchorEl}
            activeFilterCount={activeFilterCount}
            libraryOnly={libraryOnly}
            onOpenSort={openSortMenu}
            onCloseSort={closeSortMenu}
            onSelectSort={selectSort}
            onOpenFilters={() => { setActiveFilter('players'); openFilterDrawer(); }}
            onToggleLibrary={(event) => { toggleAllBoardGames(event.target.checked); setCurrentPage(1); }}
          />

          <FilterDrawer
            open={filterDrawerOpen}
            onClose={closeFilterDrawer}
            onClearAll={handleClearAll}
            isRecommendation={isRecommendation}
            isPlayersFiltered={isPlayersFiltered}
            isWeightFiltered={isWeightFiltered}
            isMechanicsFiltered={isMechanicsFiltered}
            isCategoriesFiltered={isCategoriesFiltered}
            onToggleFilter={handleToggleFilter}
            activeFilter={activeFilter}
            sortBy={sortBy}
            onSortChange={setSortBy}
            playerOptions={playerOptions}
            onPlayerCountChange={handlePlayerCountChange}
            onPlayerRecChange={handlePlayerRecChange}
            weight={weight}
            onWeightToggle={handleWeightToggle}
            popularMechanics={popularMechanics}
            selectedMechanics={selectedMechanics}
            onMechanicToggle={handleMechanicToggle}
            popularCategories={popularCategories}
            selectedCategories={selectedCategories}
            onCategoryToggle={handleCategoryToggle}
          />

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
              <ActiveFilterChips
                selectedDesigners={selectedDesigners}
                selectedArtists={selectedArtists}
                onRemove={handleRemoveFilter}
              />
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

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {isRecommendation
            ? `${totalGames.toLocaleString()} recommendation${totalGames !== 1 ? 's' : ''}`
            : `${totalGames.toLocaleString()} game${totalGames !== 1 ? 's' : ''} found`}
        </Typography>

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
