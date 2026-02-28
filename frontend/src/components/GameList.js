import React, { useState, useEffect, memo, useContext } from 'react';
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
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import SearchIcon from '@mui/icons-material/Search';
import PeopleIcon from '@mui/icons-material/People';
import PsychologyAltOutlinedIcon from '@mui/icons-material/PsychologyAltOutlined';
import SortIcon from '@mui/icons-material/Sort';
import GameDetails from './GameDetails';
import GameCard from './GameCard';
import ConstructionIcon from '@mui/icons-material/Construction';
import CategoryIcon from '@mui/icons-material/Category';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import LikedGamesDialog from './LikedGamesDialog';
import AuthContext from '../context/AuthContext';
import { apiBaseUrl } from '../config';

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
  const [inputValue, setInputValue] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [playerOptions, setPlayerOptions] = useState({ count: null, recommendation: 'allowed' });
  const [weight, setWeight] = useState({
    beginner: false,
    midweight: false,
    heavy: false
  });
  const [selectedDesigners, setSelectedDesigners] = useState([]);
  const [selectedArtists, setSelectedArtists] = useState([]);
  const [selectedMechanics, setSelectedMechanics] = useState([]);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedGame, setSelectedGame] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [sortBy, setSortBy] = useState('rank');
  const [currentPage, setCurrentPage] = useState(1);
  const gamesPerPage = 24;
  const [activeFilter, setActiveFilter] = useState(null);
  const [isRecommendationLoading, setIsRecommendationLoading] = useState(false);

  const { user } = useContext(AuthContext);

  const [likedGames, setLikedGames] = useState([]);
  const [dislikedGames, setDislikedGames] = useState([]);
  const [isLikedGamesDialogOpen, setIsLikedGamesDialogOpen] = useState(false);
  const [gameList, setGameList] = useState([]);
  const [totalGames, setTotalGames] = useState(0);
  const [isRecommendation, setIsRecommendation] = useState(false);
  const [allRecommendations, setAllRecommendations] = useState([]);
  const [paxGameIds, setPaxGameIds] = useState([]); // Store PAX game IDs for filtering
  const [paxOnly, setPaxOnly] = useState(true);
  const [showNonLibraryNotification, setShowNonLibraryNotification] = useState(false);
  const [recommendationNotice, setRecommendationNotice] = useState(null);
  const [hasSeenNonLibraryMessage, setHasSeenNonLibraryMessage] = useState(
    localStorage.getItem('hasSeenNonLibraryMessage') === 'true'
  );
  
  // New states for separated recommendation workflow
  const [hasRecommendations, setHasRecommendations] = useState(false);
  const [showingRecommendations, setShowingRecommendations] = useState(false);
  const [recommendationsStale, setRecommendationsStale] = useState(false);

  const handleLikeGame = (game) => {
    setLikedGames(prev => {
      if (prev.find(g => g.id === game.id)) {
        return prev.filter(g => g.id !== game.id); // un-like
      } else {
        return [...prev, game]; // like
      }
    });
    setDislikedGames(prev => prev.filter(g => g.id !== game.id)); // remove from disliked
    
    // Mark recommendations as stale if we have recommendations
    if (hasRecommendations) {
      setRecommendationsStale(true);
    }
  };

  const handleDislikeGame = (game) => {
    setDislikedGames(prev => {
      if (prev.find(g => g.id === game.id)) {
        return prev.filter(g => g.id !== game.id); // un-dislike
      } else {
        return [...prev, game]; // dislike
      }
    });
    setLikedGames(prev => prev.filter(g => g.id !== game.id)); // remove from liked
    
    // Mark recommendations as stale if we have recommendations
    if (hasRecommendations) {
      setRecommendationsStale(true);
    }
  };


  const handleRecommend = async () => {
    try {
      setIsRecommendationLoading(true);
      setRecommendationNotice(null);
      const fallbackGames = response?.games || [];
      const fallbackTotal = response?.total || 0;
      const recommendationPayload = {
        liked_games: likedGames.map(g => g.id),
        disliked_games: dislikedGames.map(g => g.id),
        limit: 200, // Large number for client-side filtering
      };
      const allResponse = await axios.post(`${apiBaseUrl}/recommendations`, {
        ...recommendationPayload,
        pax_only: false
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
    } finally {
      setIsRecommendationLoading(false);
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
    setPaxOnly(true);
    
    // Reset recommendation states
    setHasRecommendations(false);
    setShowingRecommendations(false);
    setRecommendationsStale(false);
    setAllRecommendations([]);
    setRecommendationNotice(null);
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

  // Remove page parameter from URL on mount
  useEffect(() => {
    if (searchParams.has('page')) {
      const nextSearchParams = new URLSearchParams(searchParams);
      nextSearchParams.delete('page');
      setSearchParams(nextSearchParams);
    }
  }, [searchParams, setSearchParams]);

  // Fetch mechanics by frequency
  const { data: popularMechanics = [] } = useQuery({
    // queryKey: ['mechanics_by_frequency'],
    queryKey: ['mechanics_alphabetically'],    
    queryFn: async () => {
      // const response = await axios.get(`${apiBaseUrl}/mechanics/by_frequency`);
      const response = await axios.get(`${apiBaseUrl}/mechanics/`);
      return response.data;
    },
    staleTime: 24 * 60 * 60 * 1000, // 24 hours
  });

  const { data: popularCategories = [] } = useQuery({
    // queryKey: ['categories_by_frequency'],
    queryKey: ['categories_alphabetically'],
    queryFn: async () => {
      // const response = await axios.get(`${apiBaseUrl}/categories/by_frequency`);
      const response = await axios.get(`${apiBaseUrl}/categories/`);
      return response.data;
    },
    staleTime: 24 * 60 * 60 * 1000, // 24 hours
  });

  // Fetch games with filters
  const { data: response = { games: [], total: 0 }, isLoading, error, isFetching } = useQuery({
    queryKey: ['games', searchTerm, playerOptions, selectedDesigners, selectedArtists, selectedMechanics, selectedCategories, weight, sortBy, currentPage, paxOnly],
    queryFn: async () => {
      const params = {
        limit: gamesPerPage,
        skip: (currentPage - 1) * gamesPerPage,
        sort_by: sortBy,
        pax_only: paxOnly
      };

      if (searchTerm) params.search = searchTerm;

      if (playerOptions.count) {
        params.players = playerOptions.count;
        if (playerOptions.recommendation && playerOptions.recommendation !== 'allowed') {
          params.recommendations = playerOptions.recommendation;
        }
      }

      if (selectedDesigners.length > 0) {
        params.designer_id = selectedDesigners.map(d => d.boardgamedesigner_id).join(',');
      }

      if (selectedArtists.length > 0) {
        params.artist_id = selectedArtists.map(a => a.boardgameartist_id).join(',');
      }

      if (selectedMechanics.length > 0) {
        params.mechanics = selectedMechanics.map(m => m.boardgamemechanic_id).join(',');
      }

      if (selectedCategories.length > 0) {
        params.categories = selectedCategories.map(c => c.boardgamecategory_id).join(',');
      }

      const activeWeights = Object.entries(weight)
        .filter(([_, checked]) => checked)
        .map(([key]) => key);
      
      if (activeWeights.length > 0) {
        params.weight = activeWeights.join(',');
      }

      const response = await axios.get(`${apiBaseUrl}/games/`, { params });
      return response.data;
    },
    keepPreviousData: true,
    enabled: !isRecommendation, // Disable when showing recommendations
  });

  useEffect(() => {
    if (!isRecommendation && response?.games) {
      setGameList(response.games);
      setTotalGames(response.total);
    }
  }, [response, isRecommendation]);

  // Fetch PAX game IDs once on mount
  useEffect(() => {
    const fetchPaxGameIds = async () => {
      try {
        const response = await axios.get(`${apiBaseUrl}/pax_game_ids/`);
        setPaxGameIds(response.data); // Should be an array of IDs
      } catch (err) {
        console.error('Failed to fetch PAX game IDs:', err);
      }
    };
    fetchPaxGameIds();
  }, []);

  useEffect(() => {
    if (showingRecommendations && hasRecommendations) {
      let newGameList = allRecommendations;
      if (paxOnly && paxGameIds.length > 0) {
        const paxSet = new Set(paxGameIds);
        newGameList = allRecommendations.filter(game => paxSet.has(game.id));
      }
      setGameList(newGameList);
      setTotalGames(newGameList.length);
      setCurrentPage(1);
      setIsRecommendation(true);
    } else {
      setIsRecommendation(false);
    }
  }, [showingRecommendations, hasRecommendations, paxOnly, allRecommendations, paxGameIds]);

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

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, playerOptions, selectedDesigners, selectedArtists, selectedMechanics, selectedCategories, weight, sortBy]);

  const handlePageChange = (event, newPage) => {
    setCurrentPage(newPage);
  };

  const handleGameClick = async (game) => {
    try {
      const response = await axios.get(`${apiBaseUrl}/games/${game.id}/`);
      setSelectedGame(response.data);
      setDetailsOpen(true);
    } catch (err) {
      console.error('Failed to fetch game details:', err);
    }
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
              onLike={() => handleLikeGame(game)}
              onDislike={() => handleDislikeGame(game)}
              isPaxGame={paxGameIds.includes(game.id)}
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
              }}
            />
          </Tooltip>

          {/* Filter Bar */}
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ flexWrap: 'wrap', gap: 1 }}>
            <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ gap: 1 }}>
              <Tooltip title="Show non-library games for recommendations and information">
                <FormControlLabel
                  control={<Switch checked={!paxOnly} onChange={(e) => {
                    const showNonLibrary = e.target.checked;
                    setPaxOnly(!showNonLibrary);
                    setShowNonLibraryNotification(false);
                    if (showNonLibrary && !hasSeenNonLibraryMessage) {
                      setShowNonLibraryNotification(true);
                      setHasSeenNonLibraryMessage(true);
                      localStorage.setItem('hasSeenNonLibraryMessage', 'true');
                    }
                  }} />}
                  label="All Board Games"
                  sx={{ mr: 2 }}
                  data-tour="pax-toggle"
                />
              </Tooltip>
              <Tooltip title={isRecommendation ? "Sort is disabled in recommendation mode" : sortButtonLabel}>
                <Button
                  variant={isSortFiltered || activeFilter === 'sort' ? 'contained' : 'outlined'}
                  onClick={() => handleToggleFilter('sort')}
                  startIcon={<SortIcon />}
                  disabled={isRecommendation}
                  sx={{ textTransform: 'none' }}
                >
                  {sortButtonLabel}
                </Button>
              </Tooltip>
              <Tooltip title={isRecommendation ? "Player filter is disabled in recommendation mode" : playerButtonLabel}>
                <Button
                  variant={isPlayersFiltered || activeFilter === 'players' ? 'contained' : 'outlined'}
                  onClick={() => handleToggleFilter('players')}
                  startIcon={<PeopleIcon />}
                  disabled={isRecommendation}
                  sx={{ textTransform: 'none' }}
                  data-tour="player-filter"
                >
                  {playerButtonLabel}
                </Button>
              </Tooltip>
              <Tooltip title={isRecommendation ? "Weight filter is disabled in recommendation mode" : weightButtonLabel}>
                <Button
                  variant={isWeightFiltered || activeFilter === 'weight' ? 'contained' : 'outlined'}
                  onClick={() => handleToggleFilter('weight')}
                  startIcon={<PsychologyAltOutlinedIcon />}
                  disabled={isRecommendation}
                  sx={{ textTransform: 'none' }}
                >
                  {weightButtonLabel}
                </Button>
              </Tooltip>
              <Tooltip title={isRecommendation ? "Mechanics filter is disabled in recommendation mode" : mechanicsButtonLabel}>
                <Button
                  variant={isMechanicsFiltered || activeFilter === 'mechanics' ? 'contained' : 'outlined'}
                  onClick={() => handleToggleFilter('mechanics')}
                  startIcon={<ConstructionIcon />}
                  disabled={isRecommendation}
                  sx={{ textTransform: 'none' }}
                >
                  {mechanicsButtonLabel}
                </Button>
              </Tooltip>
              <Tooltip title={isRecommendation ? "Categories filter is disabled in recommendation mode" : categoriesButtonLabel}>
                <Button
                  variant={isCategoriesFiltered || activeFilter === 'categories' ? 'contained' : 'outlined'}
                  onClick={() => handleToggleFilter('categories')}
                  startIcon={<CategoryIcon />}
                  disabled={isRecommendation}
                  sx={{ textTransform: 'none' }}
                >
                  {categoriesButtonLabel}
                </Button>
              </Tooltip>
            </Stack>
            <Tooltip title={isRecommendation ? "Reset filters is disabled in recommendation mode" : "Clear all active filters and search"}>
              <Button onClick={handleResetFilters} size="small" disabled={isRecommendation}>
                  Reset Filters
              </Button>
            </Tooltip>
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
                        onChange={(e) => setShowingRecommendations(e.target.checked)}
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

        {isFetching && !isRecommendation && (
          <Box sx={{ width: '100%', mb: 2 }}>
            <CircularProgress size={24} />
          </Box>
        )}
        
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

        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', mt: 4, gap: 2 }}>
          <Typography variant="body2" color="text.secondary">
            {isRecommendation 
              ? `${totalGames.toLocaleString()} recommendation${totalGames !== 1 ? 's' : ''}`
              : `${totalGames.toLocaleString()} game${totalGames !== 1 ? 's' : ''} found`
            }
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

        {selectedGame && (
          <GameDetails
            game={selectedGame}
            open={detailsOpen}
            onClose={() => setDetailsOpen(false)}
            onLike={handleLikeGame}
            onDislike={handleDislikeGame}
            likedGames={likedGames}
            dislikedGames={dislikedGames}
            onFilter={handleFilter}
          />
        )}
      </Container>
      <LikedGamesDialog
        open={isLikedGamesDialogOpen}
        onClose={() => setIsLikedGamesDialogOpen(false)}
        likedGames={likedGames}
        dislikedGames={dislikedGames}
        onRemoveLike={handleLikeGame}
        onRemoveDislike={handleDislikeGame}
      />
    </>
  );
};

export default memo(GameList); 
