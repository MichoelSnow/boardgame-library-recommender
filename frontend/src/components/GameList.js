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
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
  Popover,
  MenuItem,
  MenuList,
} from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import SearchIcon from '@mui/icons-material/Search';
import SortIcon from '@mui/icons-material/Sort';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import GameDetails from './GameDetails';
import GameCard from './GameCard';
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
  useFilterTaxonomyQuery,
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

const playerCountOptions = Array.from({ length: 8 }, (_, i) => i + 1);
const PLAYER_COUNT_NINE_PLUS = '9plus';
const playtimeOptions = [15, 30, 45, 60, 90, 120, 180, 240];
const ageOptions = [5, 6, 8, 10, 12, 14];
const gameStyleOptions = [
  { value: 'any', label: 'Any' },
  { value: 'family', label: 'Family Games' },
  { value: 'children', label: "Children's Games" },
  { value: 'party', label: 'Party Games' },
];
const formatPlaytimeLabel = (minutes) =>
  minutes >= 120 ? `${minutes / 60} hours` : `${minutes} min`;

const VALID_PLAYER_RECOMMENDATIONS = new Set(['allowed', 'recommended', 'best']);
const VALID_SORT_OPTIONS = new Set(sortOptions.map((option) => option.value));
const VALID_GAME_STYLES = new Set(gameStyleOptions.map((option) => option.value));
const STYLE_CATEGORY_IDS = { party: 1030, children: 1041 };
const COOPERATIVE_MECHANIC_ID = 2023;
const FILTER_DRAWER_HISTORY_KEY = '__gameListFilterDrawer';

const parseIntegerParam = (value) => {
  if (!value) {
    return null;
  }

  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
};

const parsePlayerCountParam = (value) => {
  if (value === PLAYER_COUNT_NINE_PLUS) {
    return value;
  }

  const parsed = parseIntegerParam(value);
  return parsed !== null && parsed >= 1 && parsed <= 12 ? parsed : null;
};

const parseChoiceParam = (value, validChoices, fallback) =>
  validChoices.has(value) ? value : fallback;

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

const parseCsvStrings = (value) => (value || '')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean);

const buildPlaceholderSelection = (ids, idKey, nameKey) =>
  ids.map((id) => ({
    [idKey]: id,
    [nameKey]: '',
  }));

const buildTaxonomyPlaceholders = (ids) => ids.map((option_id) => ({
  option_id,
  label: option_id,
  group: option_id.startsWith('theme:') ? 'theme' : 'game_type',
  featured: false,
  sources: [],
}));

const buildFilterDraft = ({
  playerOptions,
  weight,
  selectedDesigners,
  selectedArtists,
  selectedMechanics,
  selectedCategories,
  selectedGameTypes,
  selectedThemes,
  maxPlaytime,
  minAge,
  gameStyle,
  cooperative,
}) => ({
  playerOptions: { ...playerOptions },
  weight: { ...weight },
  selectedDesigners: [...selectedDesigners],
  selectedArtists: [...selectedArtists],
  selectedMechanics: [...selectedMechanics],
  selectedCategories: [...selectedCategories],
  selectedGameTypes: [...selectedGameTypes],
  selectedThemes: [...selectedThemes],
  maxPlaytime,
  minAge,
  gameStyle,
  cooperative,
});

const buildEmptyFilterDraft = () => ({
  playerOptions: { count: null, recommendation: 'allowed' },
  weight: { beginner: false, midweight: false, heavy: false },
  selectedDesigners: [],
  selectedArtists: [],
  selectedMechanics: [],
  selectedCategories: [],
  selectedGameTypes: [],
  selectedThemes: [],
  maxPlaytime: null,
  minAge: null,
  gameStyle: 'any',
  cooperative: false,
});

const EMPTY_GAMES_RESPONSE = { games: [], total: 0 };

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
  isRecommendation,
  filterValues,
  draftRef,
  gameTypeOptions,
  themeOptions,
}) => {
  const [expandedSections, setExpandedSections] = useState(() => new Set(['group']));
  const [showAll, setShowAll] = useState({ gameType: false, theme: false });
  const [taxonomySearch, setTaxonomySearch] = useState({ gameType: '', theme: '' });
  const [draft, setDraft] = useState(() => buildFilterDraft(filterValues));

  const updateDraft = (updater) => {
    setDraft((previous) => {
      const next = updater(previous);
      draftRef.current = next;
      return next;
    });
  };

  const {
    playerOptions,
    maxPlaytime,
    minAge,
    weight,
    gameStyle,
    cooperative,
    selectedGameTypes,
    selectedThemes,
  } = draft;

  const groupSelectionCount =
    (playerOptions.count !== null ? 1 : 0) +
    (maxPlaytime !== null ? 1 : 0) +
    (minAge !== null ? 1 : 0) +
    Object.values(weight).filter(Boolean).length +
    (gameStyle !== 'any' ? 1 : 0) +
    (cooperative ? 1 : 0);
  const gameTypeSelectionCount = selectedGameTypes.length + draft.selectedMechanics.length;
  const themeSelectionCount = selectedThemes.length + draft.selectedCategories.length;

  const handleClearAll = () => updateDraft(() => buildEmptyFilterDraft());

  const handlePlayerCountChange = (_event, newCount) => updateDraft((previous) => ({
    ...previous,
    playerOptions: {
      ...previous.playerOptions,
      count: newCount,
    },
  }));

  const handlePlayerRecChange = (_event, newRec) => {
    if (newRec !== null) {
      updateDraft((previous) => ({
        ...previous,
        playerOptions: {
          ...previous.playerOptions,
          recommendation: newRec,
        },
      }));
    }
  };

  const handleWeightToggle = (weightKey) => updateDraft((previous) => ({
    ...previous,
    weight: {
      ...previous.weight,
      [weightKey]: !previous.weight[weightKey],
    },
  }));

  const handleMaxPlaytimeChange = (value) => updateDraft((previous) => ({
    ...previous,
    maxPlaytime: value,
  }));

  const handleMinAgeChange = (value) => updateDraft((previous) => ({
    ...previous,
    minAge: value,
  }));

  const handleGameStyleChange = (value) => updateDraft((previous) => ({
    ...previous,
    gameStyle: value,
  }));

  const handleCooperativeChange = (value) => updateDraft((previous) => ({
    ...previous,
    cooperative: value,
  }));

  const handleTaxonomyToggle = (option) => {
    const mechanicIds = new Set(
      option.sources.filter((source) => source.type === 'mechanic').map((source) => source.id)
    );
    const categoryIds = new Set(
      option.sources.filter((source) => source.type === 'category').map((source) => source.id)
    );
    updateDraft((previous) => {
      const selectionKey = option.group === 'game_type' ? 'selectedGameTypes' : 'selectedThemes';
      const isSelected = previous[selectionKey].some(
        (item) => item.option_id === option.option_id
      );
      return {
        ...previous,
        [selectionKey]: isSelected
          ? previous[selectionKey].filter((item) => item.option_id !== option.option_id)
          : [...previous[selectionKey], option],
        selectedMechanics: mechanicIds.size > 0
          ? previous.selectedMechanics.filter(
            (item) => !mechanicIds.has(item.boardgamemechanic_id)
          )
          : previous.selectedMechanics,
        selectedCategories: categoryIds.size > 0
          ? previous.selectedCategories.filter(
            (item) => !categoryIds.has(item.boardgamecategory_id)
          )
          : previous.selectedCategories,
      };
    });
  };

  const handleSectionChange = (section) => (_event, isExpanded) => {
    setExpandedSections((previous) => {
      const next = new Set(previous);
      if (isExpanded) {
        next.add(section);
      } else {
        next.delete(section);
      }
      return next;
    });
  };

  const handleTaxonomyViewToggle = (sectionKey) => {
    if (showAll[sectionKey]) {
      setTaxonomySearch((previous) => ({
        ...previous,
        [sectionKey]: '',
      }));
    }
    setShowAll((previous) => ({
      ...previous,
      [sectionKey]: !previous[sectionKey],
    }));
  };

  const renderSelectionCount = (count) => (
    count > 0 ? (
      <Chip
        label={count}
        size="small"
        color="primary"
        aria-label={`${count} selected`}
        sx={{ ml: 1, minWidth: 28 }}
      />
    ) : null
  );

  const renderPlayerControls = () => (
    <Stack spacing={1.5}>
      <Typography variant="body2" color="text.secondary">
        How many people are playing?
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        <Button
          variant={playerOptions.count === null ? 'contained' : 'outlined'}
          onClick={() => handlePlayerCountChange(null, null)}
          size="small"
          disabled={isRecommendation}
          aria-pressed={playerOptions.count === null}
        >
          Any
        </Button>
        {playerCountOptions.map((count) => (
          <Button
            key={count}
            variant={playerOptions.count === count ? 'contained' : 'outlined'}
            onClick={() => handlePlayerCountChange(null, count)}
            size="small"
            disabled={isRecommendation}
            aria-pressed={playerOptions.count === count}
          >
            {count}
          </Button>
        ))}
        <Button
          variant={playerOptions.count === PLAYER_COUNT_NINE_PLUS ? 'contained' : 'outlined'}
          onClick={() => handlePlayerCountChange(null, PLAYER_COUNT_NINE_PLUS)}
          size="small"
          disabled={isRecommendation}
          aria-pressed={playerOptions.count === PLAYER_COUNT_NINE_PLUS}
        >
          9+
        </Button>
      </Box>
      {playerOptions.count !== null && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {['allowed', 'recommended', 'best'].map((recommendation) => (
            <Button
              key={recommendation}
              size="small"
              variant={playerOptions.recommendation === recommendation ? 'contained' : 'outlined'}
              onClick={() => handlePlayerRecChange(null, recommendation)}
              disabled={isRecommendation}
              aria-pressed={playerOptions.recommendation === recommendation}
            >
              {recommendation[0].toUpperCase() + recommendation.slice(1)}
            </Button>
          ))}
        </Box>
      )}
    </Stack>
  );

  const renderComplexityControls = () => (
    <Stack spacing={1}>
      <Typography variant="body2" color="text.secondary">
        Select one or more complexity levels.
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        <Button
          size="small"
          variant={weight.beginner ? 'contained' : 'outlined'}
          onClick={() => handleWeightToggle('beginner')}
          disabled={isRecommendation}
          aria-pressed={weight.beginner}
        >
          Light (&lt; 2)
        </Button>
        <Button
          size="small"
          variant={weight.midweight ? 'contained' : 'outlined'}
          onClick={() => handleWeightToggle('midweight')}
          disabled={isRecommendation}
          aria-pressed={weight.midweight}
        >
          Medium (2–4)
        </Button>
        <Button
          size="small"
          variant={weight.heavy ? 'contained' : 'outlined'}
          onClick={() => handleWeightToggle('heavy')}
          disabled={isRecommendation}
          aria-pressed={weight.heavy}
        >
          Heavy (&gt; 4)
        </Button>
      </Box>
    </Stack>
  );

  const renderSingleSelectButtons = (options, value, onChange, formatLabel = (option) => option) => (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
      <Button
        size="small"
        variant={value === null ? 'contained' : 'outlined'}
        onClick={() => onChange(null)}
        disabled={isRecommendation}
        aria-pressed={value === null}
      >
        Any
      </Button>
      {options.map((option) => (
        <Button
          key={option}
          size="small"
          variant={value === option ? 'contained' : 'outlined'}
          onClick={() => onChange(option)}
          disabled={isRecommendation}
          aria-pressed={value === option}
        >
          {formatLabel(option)}
        </Button>
      ))}
    </Box>
  );

  const renderTaxonomyControls = (options, selected, sectionKey, sectionLabel) => {
    const query = taxonomySearch[sectionKey].trim().toLowerCase();
    const visibleOptions = (showAll[sectionKey] ? options : options.filter((option) => option.featured))
      .filter((option) => {
        if (!query) return true;
        const sourceNames = option.sources.map((source) => source.name).join(' ');
        return `${option.label} ${sourceNames}`.toLowerCase().includes(query);
      });
    const selectedIds = new Set(selected.map((option) => option.option_id));

    return (
      <Stack spacing={1.5}>
        {showAll[sectionKey] && (
          <TextField
            size="small"
            fullWidth
            label={`Search ${sectionLabel}`}
            value={taxonomySearch[sectionKey]}
            onChange={(event) => setTaxonomySearch((previous) => ({
              ...previous,
              [sectionKey]: event.target.value,
            }))}
            inputProps={{ 'aria-label': `Search ${sectionLabel}` }}
          />
        )}
        <Grid container spacing={1}>
          {visibleOptions.map((option) => (
            <Grid size={{ xs: 6, sm: 4 }} key={option.option_id}>
              <Button
                fullWidth
                variant={selectedIds.has(option.option_id) ? 'contained' : 'outlined'}
                onClick={() => handleTaxonomyToggle(option)}
                size="small"
                disabled={isRecommendation}
                aria-pressed={selectedIds.has(option.option_id)}
                sx={{
                  textAlign: 'center',
                  minHeight: 44,
                  height: '100%',
                  display: 'flex',
                  justifyContent: 'center',
                  fontSize: '0.8rem',
                  lineHeight: 1.2,
                  p: 1,
                }}
              >
                {option.label}
              </Button>
            </Grid>
          ))}
        </Grid>
        <Button
          size="small"
          variant="text"
          onClick={() => handleTaxonomyViewToggle(sectionKey)}
          disabled={isRecommendation}
        >
          {showAll[sectionKey] ? `Show Featured ${sectionLabel}` : `Show All ${sectionLabel}`}
        </Button>
      </Stack>
    );
  };

  return (
    <Drawer
      anchor="left"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: { xs: '90vw', sm: 420 },
          maxWidth: '100vw',
          display: 'flex',
          flexDirection: 'column',
        },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2, flexShrink: 0 }}>
        <Typography variant="h6">Filter Games</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Button onClick={handleClearAll} size="small">Clear All</Button>
          <IconButton aria-label="Close filters" onClick={onClose}><CloseIcon /></IconButton>
        </Box>
      </Box>
      <Divider />
      <Box sx={{ overflowY: 'auto', flex: 1, p: 1 }}>
        <Accordion
          disableGutters
          expanded={expandedSections.has('group')}
          onChange={handleSectionChange('group')}
          disabled={isRecommendation}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <Typography sx={{ fontWeight: 600 }}>Group &amp; Requirements</Typography>
              {renderSelectionCount(groupSelectionCount)}
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={2}>
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>Players</Typography>
                {renderPlayerControls()}
              </Box>
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>Complexity</Typography>
                {renderComplexityControls()}
              </Box>
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>Maximum Play Time</Typography>
                {renderSingleSelectButtons(playtimeOptions, maxPlaytime, handleMaxPlaytimeChange, formatPlaytimeLabel)}
              </Box>
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>Minimum Age</Typography>
                {renderSingleSelectButtons(ageOptions, minAge, handleMinAgeChange, (option) => `${option}+`)}
              </Box>
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>Game Style</Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {gameStyleOptions.map((option) => (
                    <Button
                      key={option.value}
                      size="small"
                      variant={gameStyle === option.value ? 'contained' : 'outlined'}
                      onClick={() => handleGameStyleChange(option.value)}
                      disabled={isRecommendation}
                      aria-pressed={gameStyle === option.value}
                    >
                      {option.label}
                    </Button>
                  ))}
                </Box>
              </Box>
              <Button
                size="small"
                variant={cooperative ? 'contained' : 'outlined'}
                onClick={() => handleCooperativeChange(!cooperative)}
                disabled={isRecommendation}
                aria-pressed={cooperative}
                sx={{ alignSelf: 'flex-start' }}
              >
                Cooperative games only
              </Button>
            </Stack>
          </AccordionDetails>
        </Accordion>

        <Accordion
          disableGutters
          expanded={expandedSections.has('gameType')}
          onChange={handleSectionChange('gameType')}
          disabled={isRecommendation}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <Typography sx={{ fontWeight: 600 }}>Game Type</Typography>
              {renderSelectionCount(gameTypeSelectionCount)}
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            {renderTaxonomyControls(gameTypeOptions, selectedGameTypes, 'gameType', 'Game Types')}
          </AccordionDetails>
        </Accordion>

        <Accordion
          disableGutters
          expanded={expandedSections.has('theme')}
          onChange={handleSectionChange('theme')}
          disabled={isRecommendation}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <Typography sx={{ fontWeight: 600 }}>Theme &amp; Setting</Typography>
              {renderSelectionCount(themeSelectionCount)}
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            {renderTaxonomyControls(themeOptions, selectedThemes, 'theme', 'Themes')}
          </AccordionDetails>
        </Accordion>
      </Box>
    </Drawer>
  );
};

const ActiveFilterChips = ({ chips, onRemove, onShowMore }) => {
  if (chips.length === 0) {
    return null;
  }

  const visibleChips = chips.slice(0, 3);
  const hiddenCount = chips.length - visibleChips.length;

  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center', mb: 1 }}>
      {visibleChips.map((chip) => (
        <Chip
          key={chip.key}
          label={chip.label}
          onClick={() => onRemove(chip.type, chip.id)}
          onDelete={() => onRemove(chip.type, chip.id)}
          deleteIcon={<CloseIcon fontSize="small" />}
          aria-label={`Remove ${chip.label} filter`}
          color="primary"
          clickable
          sx={{
            minHeight: 44,
            '& .MuiChip-deleteIcon': { fontSize: '1.2rem' },
          }}
        />
      ))}
      {hiddenCount > 0 && (
        <Button
          variant="text"
          onClick={onShowMore}
          sx={{ minHeight: 44, whiteSpace: 'nowrap' }}
        >
          +{hiddenCount} more
        </Button>
      )}
    </Box>
  );
};

const GameList = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSearchValue = searchParams.get('search') || '';
  const initialPlayerCount = parsePlayerCountParam(searchParams.get('players'));
  const initialPlayerRecommendation = searchParams.get('player_rec');
  const initialWeightValues = new Set(
    (searchParams.get('weight') || '')
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
  );
  const initialMechanicIds = parseCsvIntegers(searchParams.get('mechanics'));
  const initialCategoryIds = parseCsvIntegers(searchParams.get('categories'));
  const initialGameTypeIds = parseCsvStrings(searchParams.get('game_types'));
  const initialThemeIds = parseCsvStrings(searchParams.get('themes'));
  const initialMaxPlaytimeValue = parseIntegerParam(searchParams.get('max_playtime'));
  const initialMaxPlaytime = playtimeOptions.includes(initialMaxPlaytimeValue)
    ? initialMaxPlaytimeValue
    : null;
  const initialMinAgeValue = parseIntegerParam(searchParams.get('min_age'));
  const initialMinAge = ageOptions.includes(initialMinAgeValue)
    ? initialMinAgeValue
    : null;
  const initialGameStyle = parseChoiceParam(
    searchParams.get('game_style'),
    VALID_GAME_STYLES,
    'any'
  );
  const initialCooperative = searchParams.get('cooperative') === 'true';
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
  const [selectedGameTypes, setSelectedGameTypes] = useState(
    buildTaxonomyPlaceholders(initialGameTypeIds)
  );
  const [selectedThemes, setSelectedThemes] = useState(
    buildTaxonomyPlaceholders(initialThemeIds)
  );
  const [maxPlaytime, setMaxPlaytime] = useState(initialMaxPlaytime);
  const [minAge, setMinAge] = useState(initialMinAge);
  const [gameStyle, setGameStyle] = useState(initialGameStyle);
  const [cooperative, setCooperative] = useState(initialCooperative);
  const [selectedGameId, setSelectedGameId] = useState(null);
  const [selectedGamePreview, setSelectedGamePreview] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [sortBy, setSortBy] = useState(
    VALID_SORT_OPTIONS.has(initialSortBy) ? initialSortBy : 'rank'
  );
  const [currentPage, setCurrentPage] = useState(1);
  const gamesPerPage = 24;
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const filterDraftRef = useRef(null);
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
  } = useRecommendationSessionState({ user });
  const selectedMechanicIds = selectedMechanics.map(
    (item) => item.boardgamemechanic_id
  );
  const selectedCategoryIds = selectedCategories.map(
    (item) => item.boardgamecategory_id
  );
  const selectedTaxonomyMechanicIds = selectedGameTypes
    .concat(selectedThemes)
    .flatMap((option) => option.sources
      .filter((source) => source.type === 'mechanic')
      .map((source) => source.id));
  const selectedTaxonomyCategoryIds = selectedGameTypes
    .concat(selectedThemes)
    .flatMap((option) => option.sources
      .filter((source) => source.type === 'category')
      .map((source) => source.id));
  const selectedDetailMechanicIds = [...new Set(selectedMechanicIds
    .concat(selectedTaxonomyMechanicIds)
    .concat(cooperative ? [COOPERATIVE_MECHANIC_ID] : []))];
  const selectedDetailCategoryIds = [...new Set(selectedCategoryIds
    .concat(selectedTaxonomyCategoryIds)
    .concat(gameStyle in STYLE_CATEGORY_IDS ? [STYLE_CATEGORY_IDS[gameStyle]] : []))];
  const recommendationMutation = useRecommendationMutation();
  const isRecommendationLoading = recommendationMutation.isPending;

  const { data: popularMechanics = [] } = useMechanicsQuery();
  const { data: popularCategories = [] } = useCategoriesQuery();
  const { data: taxonomyOptions = [] } = useFilterTaxonomyQuery();
  const gameTypeOptions = taxonomyOptions.filter((option) => option.group === 'game_type');
  const themeOptions = taxonomyOptions.filter((option) => option.group === 'theme');
  const selectedGameTypeIds = selectedGameTypes.map((option) => option.option_id);
  const selectedThemeIds = selectedThemes.map((option) => option.option_id);
  const { data: libraryGameIds = [] } = useLibraryGameIdsQuery();

  const {
    data: response = EMPTY_GAMES_RESPONSE,
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
    selectedGameTypeIds,
    selectedThemeIds,
    weight,
    maxPlaytime,
    minAge,
    gameStyle,
    cooperative,
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
          { queryKey: ['categories_alphabetically'], type: 'active' },
          { queryKey: ['filter_taxonomy'], type: 'active' }
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

    if (selectedGameTypeIds.length > 0) {
      nextSearchParams.set('game_types', selectedGameTypeIds.join(','));
    } else {
      nextSearchParams.delete('game_types');
    }

    if (selectedThemeIds.length > 0) {
      nextSearchParams.set('themes', selectedThemeIds.join(','));
    } else {
      nextSearchParams.delete('themes');
    }

    if (maxPlaytime !== null) {
      nextSearchParams.set('max_playtime', String(maxPlaytime));
    } else {
      nextSearchParams.delete('max_playtime');
    }

    if (minAge !== null) {
      nextSearchParams.set('min_age', String(minAge));
    } else {
      nextSearchParams.delete('min_age');
    }

    if (gameStyle !== 'any') {
      nextSearchParams.set('game_style', gameStyle);
    } else {
      nextSearchParams.delete('game_style');
    }

    if (cooperative) {
      nextSearchParams.set('cooperative', 'true');
    } else {
      nextSearchParams.delete('cooperative');
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
    selectedMechanicIds,
    selectedGameTypeIds,
    selectedThemeIds,
    setSearchParams,
    sortBy,
    weight,
    maxPlaytime,
    minAge,
    gameStyle,
    cooperative,
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
    if (!taxonomyOptions.length) {
      return;
    }

    const optionsById = new Map(taxonomyOptions.map((option) => [option.option_id, option]));
    const sourceOptions = new Map();
    taxonomyOptions.forEach((option) => option.sources.forEach((source) => {
      sourceOptions.set(`${source.type}:${source.id}`, option);
    }));

    setSelectedGameTypes((previous) => {
      let changed = false;
      const next = previous.map((option) => {
        const resolved = optionsById.get(option.option_id);
        if (resolved && resolved !== option) {
          changed = true;
          return resolved;
        }
        return option;
      });
      return changed ? next : previous;
    });
    setSelectedThemes((previous) => {
      let changed = false;
      const next = previous.map((option) => {
        const resolved = optionsById.get(option.option_id);
        if (resolved && resolved !== option) {
          changed = true;
          return resolved;
        }
        return option;
      });
      return changed ? next : previous;
    });

    const promoteLegacySources = (sourceType, selected, setLegacy) => {
      const promoted = [];
      const unresolved = [];
      selected.forEach((source) => {
        const option = sourceOptions.get(`${sourceType}:${source[sourceType === 'mechanic' ? 'boardgamemechanic_id' : 'boardgamecategory_id']}`);
        if (option) {
          promoted.push(option);
        } else {
          unresolved.push(source);
        }
      });
      if (promoted.length > 0) {
        const setters = {
          game_type: setSelectedGameTypes,
          theme: setSelectedThemes,
        };
        promoted.forEach((option) => setters[option.group]((previous) => {
          const byId = new Map(previous.map((item) => [item.option_id, item]));
          byId.set(option.option_id, option);
          return Array.from(byId.values());
        }));
      }
      if (unresolved.length !== selected.length) {
        setLegacy(unresolved);
      }
    };

    promoteLegacySources('mechanic', selectedMechanics, setSelectedMechanics);
    promoteLegacySources('category', selectedCategories, setSelectedCategories);
    // This effect intentionally runs only when the server contract becomes available.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taxonomyOptions]);

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
  const complexityLabels = {
    beginner: 'Complexity: Light',
    midweight: 'Complexity: Medium',
    heavy: 'Complexity: Heavy',
  };
  const activeFilterChips = [
    ...(isPlayersFiltered
      ? [{
          key: 'players',
          label: `${playerOptions.count === PLAYER_COUNT_NINE_PLUS ? '9+' : playerOptions.count} players${playerOptions.recommendation !== 'allowed' ? ` · ${playerOptions.recommendation[0].toUpperCase()}${playerOptions.recommendation.slice(1)}` : ''}`,
          type: 'players',
          id: null,
        }]
      : []),
    ...(maxPlaytime !== null
      ? [{
          key: 'max-playtime',
          label: `Up to ${formatPlaytimeLabel(maxPlaytime)}`,
          type: 'max_playtime',
          id: null,
        }]
      : []),
    ...(minAge !== null
      ? [{
          key: 'min-age',
          label: `Age ${minAge}+`,
          type: 'min_age',
          id: null,
        }]
      : []),
    ...Object.entries(weight)
      .filter(([, selected]) => selected)
      .map(([key]) => ({
        key: `weight-${key}`,
        label: complexityLabels[key],
        type: 'weight',
        id: key,
      })),
    ...(gameStyle !== 'any'
      ? [{
          key: 'game-style',
          label: gameStyleOptions.find((option) => option.value === gameStyle)?.label || gameStyle,
          type: 'game_style',
          id: null,
        }]
      : []),
    ...(cooperative
      ? [{
          key: 'cooperative',
          label: 'Cooperative',
          type: 'cooperative',
          id: null,
        }]
      : []),
    ...selectedGameTypes.map((option) => ({
      key: `game-type-${option.option_id}`,
      label: `Game Type: ${option.label}`,
      type: 'game_type',
      id: option.option_id,
    })),
    ...selectedThemes.map((option) => ({
      key: `theme-${option.option_id}`,
      label: `Theme: ${option.label}`,
      type: 'theme',
      id: option.option_id,
    })),
    ...selectedMechanics.map((mechanic) => ({
      key: `mechanic-${mechanic.boardgamemechanic_id}`,
      label: `Mechanic: ${mechanic.boardgamemechanic_name || mechanic.boardgamemechanic_id}`,
      type: 'mechanic',
      id: mechanic.boardgamemechanic_id,
    })),
    ...selectedCategories.map((category) => ({
      key: `category-${category.boardgamecategory_id}`,
      label: `Category: ${category.boardgamecategory_name || category.boardgamecategory_id}`,
      type: 'category',
      id: category.boardgamecategory_id,
    })),
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
  const activeFilterCount = activeFilterChips.length;

  const closeSearch = () => {
    setInputValue('');
    setSearchTerm('');
    setSearchOpen(false);
  };

  const commitFilterDraft = useCallback(() => {
    const filterDraft = filterDraftRef.current;
    if (!filterDraft) {
      return;
    }

    setPlayerOptions(filterDraft.playerOptions);
    setWeight(filterDraft.weight);
    setSelectedDesigners(filterDraft.selectedDesigners);
    setSelectedArtists(filterDraft.selectedArtists);
    setSelectedMechanics(filterDraft.selectedMechanics);
    setSelectedCategories(filterDraft.selectedCategories);
    setSelectedGameTypes(filterDraft.selectedGameTypes);
    setSelectedThemes(filterDraft.selectedThemes);
    setMaxPlaytime(filterDraft.maxPlaytime);
    setMinAge(filterDraft.minAge);
    setGameStyle(filterDraft.gameStyle);
    setCooperative(filterDraft.cooperative);
    setCurrentPage(1);
    filterDraftRef.current = null;
  }, []);

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

    filterDraftRef.current = buildFilterDraft({
      playerOptions,
      weight,
      selectedDesigners,
      selectedArtists,
      selectedMechanics,
      selectedCategories,
      selectedGameTypes,
      selectedThemes,
      maxPlaytime,
      minAge,
      gameStyle,
      cooperative,
    });
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

    commitFilterDraft();
    setFilterDrawerOpen(false);
    if (window.history.state?.[FILTER_DRAWER_HISTORY_KEY]) {
      window.history.back();
    }
  };

  useEffect(() => {
    const handlePopState = () => {
      commitFilterDraft();
      setFilterDrawerOpen(false);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [commitFilterDraft]);

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [
    searchTerm,
    playerOptions,
    selectedDesigners,
    selectedArtists,
    selectedMechanics,
    selectedCategories,
    selectedGameTypes,
    selectedThemes,
    weight,
    maxPlaytime,
    minAge,
    gameStyle,
    cooperative,
    sortBy,
  ]);

  const handlePageChange = (event, newPage) => {
    setCurrentPage(newPage);
    window.scrollTo(0, 0);
  };

  const handleGameClick = (game) => {
    setSelectedGameId(game.id);
    setSelectedGamePreview(game);
    setDetailsOpen(true);
  };

  const handleTaxonomyToggle = (option) => {
    const setSelection = option.group === 'game_type' ? setSelectedGameTypes : setSelectedThemes;
    setSelection((previous) => {
      const isSelected = previous.some((item) => item.option_id === option.option_id);
      return isSelected
        ? previous.filter((item) => item.option_id !== option.option_id)
        : [...previous, option];
    });

    const mechanicIds = new Set(
      option.sources.filter((source) => source.type === 'mechanic').map((source) => source.id)
    );
    const categoryIds = new Set(
      option.sources.filter((source) => source.type === 'category').map((source) => source.id)
    );
    if (mechanicIds.size > 0) {
      setSelectedMechanics((previous) => previous.filter(
        (item) => !mechanicIds.has(item.boardgamemechanic_id)
      ));
    }
    if (categoryIds.size > 0) {
      setSelectedCategories((previous) => previous.filter(
        (item) => !categoryIds.has(item.boardgamecategory_id)
      ));
    }
  };

  const handleFilter = (type, id, name) => {
    if (type === 'game') {
      handleGameClick({ id });
    } else if (type === 'taxonomy') {
      const taxonomyOption = taxonomyOptions.find((option) => option.option_id === id);
      if (taxonomyOption) {
        handleTaxonomyToggle(taxonomyOption);
      }
    } else if (type === 'style') {
      setGameStyle((previous) => (previous === id ? 'any' : id));
    } else if (type === 'cooperative') {
      setCooperative((previous) => !previous);
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
      if (id === COOPERATIVE_MECHANIC_ID) {
        setCooperative((previous) => !previous);
        return;
      }
      const taxonomyOption = taxonomyOptions.find((option) => option.sources.some(
        (source) => source.type === 'mechanic' && source.id === id
      ));
      if (taxonomyOption) {
        handleTaxonomyToggle(taxonomyOption);
        return;
      }
      setSelectedMechanics(prev => {
        const exists = prev.some(m => m.boardgamemechanic_id === id);
        if (exists) {
          return prev.filter(m => m.boardgamemechanic_id !== id);
        } else {
          return [...prev, { boardgamemechanic_id: id, boardgamemechanic_name: name }];
        }
      });
    } else if (type === 'category') {
      const style = Object.entries(STYLE_CATEGORY_IDS).find(([, categoryId]) => categoryId === id)?.[0];
      if (style) {
        setGameStyle((previous) => (previous === style ? 'any' : style));
        return;
      }
      const taxonomyOption = taxonomyOptions.find((option) => option.sources.some(
        (source) => source.type === 'category' && source.id === id
      ));
      if (taxonomyOption) {
        handleTaxonomyToggle(taxonomyOption);
        return;
      }
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
    if (type === 'players') {
      setPlayerOptions({ count: null, recommendation: 'allowed' });
    } else if (type === 'weight') {
      setWeight((previous) => ({ ...previous, [id]: false }));
    } else if (type === 'max_playtime') {
      setMaxPlaytime(null);
    } else if (type === 'min_age') {
      setMinAge(null);
    } else if (type === 'game_style') {
      setGameStyle('any');
    } else if (type === 'cooperative') {
      setCooperative(false);
    } else if (type === 'designer') {
      setSelectedDesigners(prev => prev.filter(d => d.boardgamedesigner_id !== id));
    } else if (type === 'artist') {
      setSelectedArtists(prev => prev.filter(a => a.boardgameartist_id !== id));
    } else if (type === 'mechanic') {
      setSelectedMechanics(prev => prev.filter(m => m.boardgamemechanic_id !== id));
    } else if (type === 'category') {
      setSelectedCategories(prev => prev.filter(c => c.boardgamecategory_id !== id));
    } else if (type === 'game_type') {
      setSelectedGameTypes(prev => prev.filter((option) => option.option_id !== id));
    } else if (type === 'theme') {
      setSelectedThemes(prev => prev.filter((option) => option.option_id !== id));
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
            onOpenFilters={openFilterDrawer}
            onToggleLibrary={(event) => { toggleAllBoardGames(event.target.checked); setCurrentPage(1); }}
          />

          <FilterDrawer
            key={filterDrawerOpen ? 'open' : 'closed'}
            open={filterDrawerOpen}
            onClose={closeFilterDrawer}
            isRecommendation={isRecommendation}
            filterValues={buildFilterDraft({
              playerOptions,
              weight,
              selectedDesigners,
              selectedArtists,
              selectedMechanics,
              selectedCategories,
              selectedGameTypes,
              selectedThemes,
              maxPlaytime,
              minAge,
              gameStyle,
              cooperative,
            })}
            draftRef={filterDraftRef}
            gameTypeOptions={gameTypeOptions}
            themeOptions={themeOptions}
          />

          <ActiveFilterChips
            chips={activeFilterChips}
            onRemove={handleRemoveFilter}
            onShowMore={openFilterDrawer}
          />

          {/* Recommendation actions */}
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
            selectedMechanicIds={selectedDetailMechanicIds}
            selectedCategoryIds={selectedDetailCategoryIds}
            taxonomyOptions={taxonomyOptions}
            selectedGameTypeIds={selectedGameTypeIds}
            selectedThemeIds={selectedThemeIds}
            selectedGameStyle={gameStyle}
            cooperativeSelected={cooperative}
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
