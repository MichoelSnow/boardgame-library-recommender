import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Grid,
  Chip,
  Divider,
  CircularProgress,
  IconButton,
  Tooltip,
  Alert,
} from '@mui/material';
import GameCard from './GameCard';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import ThumbDownIcon from '@mui/icons-material/ThumbDown';
import ThumbUpOutlinedIcon from '@mui/icons-material/ThumbUpOutlined';
import ThumbDownOutlinedIcon from '@mui/icons-material/ThumbDownOutlined';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import EmergencyIcon from '@mui/icons-material/Emergency';
import PeopleIcon from '@mui/icons-material/People';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PsychologyAltOutlinedIcon from '@mui/icons-material/PsychologyAltOutlined';
import StarBorderOutlinedIcon from '@mui/icons-material/StarBorderOutlined';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ChildCareIcon from '@mui/icons-material/ChildCare';
import { placeholderImagePath } from '../config';
import { buildGameDetailImageCandidates } from '../utils/imageUrls';
import { decodeGameDescription } from '../utils/textEncoding';
import { useGameRecommendationsQuery } from '../hooks/useGameListQueries';

const DEFAULT_IMAGE_BG_COLOR = '#f5f5f5';

const extractAccentColor = (img) => {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx || !img?.width || !img?.height) {
    return DEFAULT_IMAGE_BG_COLOR;
  }
  try {
    const sourceWidth = img.naturalWidth || img.width;
    const sourceHeight = img.naturalHeight || img.height;
    const sampleSize = 50;
    const sampleWidth = Math.max(1, Math.min(sampleSize, sourceWidth));
    const sampleHeight = Math.max(1, Math.min(sampleSize, sourceHeight));

    canvas.width = sampleWidth;
    canvas.height = sampleHeight;
    ctx.drawImage(img, 0, 0, sourceWidth, sourceHeight, 0, 0, sampleWidth, sampleHeight);

    const imageData = ctx.getImageData(0, 0, sampleWidth, sampleHeight).data;
    let r = 0;
    let g = 0;
    let b = 0;
    const total = imageData.length / 4;
    if (!total) {
      return DEFAULT_IMAGE_BG_COLOR;
    }

    for (let i = 0; i < imageData.length; i += 4) {
      r += imageData[i];
      g += imageData[i + 1];
      b += imageData[i + 2];
    }

    r = Math.floor(r / total);
    g = Math.floor(g / total);
    b = Math.floor(b / total);

    const lighten = (color) => Math.min(255, Math.floor(color * 1.2));
    return `rgba(${lighten(r)}, ${lighten(g)}, ${lighten(b)}, 0.3)`;
  } catch (error) {
    return DEFAULT_IMAGE_BG_COLOR;
  }
};

const GameDetails = ({
  game,
  open,
  onClose,
  onFilter,
  likedGames,
  dislikedGames,
  onLike,
  onDislike,
  isLibraryGame = false,
  libraryGameIds = [],
  selectedDesignerIds = [],
  selectedArtistIds = [],
  selectedMechanicIds = [],
  selectedCategoryIds = [],
}) => {
  const [bgColor, setBgColor] = useState(DEFAULT_IMAGE_BG_COLOR);
  const [imageCandidateIndex, setImageCandidateIndex] = useState(0);
  const {
    data: recommendationResponse,
    isLoading: recommendationsLoading,
    isError: recommendationsError,
  } = useGameRecommendationsQuery({
    gameId: game?.id,
    enabled: open,
  });

  const recommendations = recommendationResponse?.data || [];
  const recommendationsAvailable =
    recommendationResponse?.headers?.['x-recommendations-available'] !== 'false';
  const libraryGameIdSet = React.useMemo(
    () => new Set(libraryGameIds),
    [libraryGameIds]
  );
  const detailImageCandidates = buildGameDetailImageCandidates({
    gameId: game?.id,
    imageUrl: game?.image,
  });
  const detailImageSrc =
    detailImageCandidates[imageCandidateIndex] || placeholderImagePath;

  useEffect(() => {
    setImageCandidateIndex(0);
  }, [game?.id, game?.image]);

  // Handle image load to extract dominant color for background (same as GameCard)
  const handleImageLoad = (event) => {
    try {
      const img = event.target;
      window.setTimeout(() => {
        setBgColor(extractAccentColor(img));
      }, 0);
    } catch (error) {
      // Cross-origin images without CORS headers cannot be sampled.
      setBgColor(DEFAULT_IMAGE_BG_COLOR);
    }
  };

  const playerCountSummary = React.useMemo(() => {
    const suggestedPlayers = Array.isArray(game?.suggested_players)
      ? game.suggested_players
      : [];
    const best = new Set();
    const recommended = new Set();

    suggestedPlayers.forEach((entry) => {
      const parsedCount = Number.parseInt(String(entry?.player_count), 10);
      if (Number.isNaN(parsedCount)) {
        return;
      }

      const level = entry?.recommendation_level;
      if (level === 'best') {
        best.add(parsedCount);
        return;
      }
      if (level === 'recommended') {
        recommended.add(parsedCount);
        return;
      }

      const bestVotes = Number(entry?.best || 0);
      const recommendedVotes = Number(entry?.recommended || 0);
      const notRecommendedVotes = Number(entry?.not_recommended || 0);

      if (bestVotes > 0 && bestVotes >= recommendedVotes && bestVotes >= notRecommendedVotes) {
        best.add(parsedCount);
      } else if (
        recommendedVotes > 0 &&
        recommendedVotes >= bestVotes &&
        recommendedVotes >= notRecommendedVotes
      ) {
        recommended.add(parsedCount);
      }
    });

    const sortedBest = [...best].sort((a, b) => a - b);
    const sortedRecommended = [...recommended]
      .filter((count) => !best.has(count))
      .sort((a, b) => a - b);

    return {
      best: sortedBest,
      recommended: sortedRecommended,
    };
  }, [game?.suggested_players]);

  if (!game) return null;

  const handleLikeClick = (e) => {
    e.stopPropagation();
    onLike(game);
  };

  const handleDislikeClick = (e) => {
    e.stopPropagation();
    onDislike(game);
  };

  const handleRecommendationClick = (rec) => {
    onFilter('game', rec.id, rec.name);
  };

  const isFilterSelected = (type, id) => {
    if (type === 'designer') {
      return selectedDesignerIds.includes(id);
    }
    if (type === 'artist') {
      return selectedArtistIds.includes(id);
    }
    if (type === 'mechanic') {
      return selectedMechanicIds.includes(id);
    }
    if (type === 'category') {
      return selectedCategoryIds.includes(id);
    }
    return false;
  };

  const renderList = (items, label, type) => {
    if (!items || items.length === 0) return null;
    const isFilterable = type === 'designer' || type === 'artist' || type === 'mechanic' || type === 'category';

    return (
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          {label}{isFilterable && ' (click to filter)'}
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {items.map((item) => {
            const name = item.boardgamemechanic_name || item.boardgamecategory_name || 
                        item.boardgamedesigner_name || item.boardgameartist_name || 
                        item.boardgamepublisher_name;
            const id = item.boardgamemechanic_id || item.boardgamecategory_id || 
                      item.boardgamedesigner_id || item.boardgameartist_id || 
                      item.boardgamepublisher_id;
            const isClickable = type === 'designer' || type === 'artist' || 
                              type === 'mechanic' || type === 'category';
            const isSelected = isClickable ? isFilterSelected(type, id) : false;
            
            return (
              <Chip
                key={id}
                label={name}
                size="small"
                color={isSelected ? 'primary' : 'default'}
                variant={isSelected ? 'filled' : 'outlined'}
                onClick={isClickable
                  ? () => {
                      onFilter(type, id, name);
                    }
                  : undefined}
                sx={isClickable ? {
                  cursor: 'pointer',
                  '&:hover': isSelected
                    ? {
                        backgroundColor: 'primary.dark',
                      }
                    : {
                        backgroundColor: 'action.hover',
                      },
                } : undefined}
              />
            );
          })}
        </Box>
      </Box>
    );
  };

  const renderRecommendations = () => {
    if (recommendationsLoading) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
          <CircularProgress />
        </Box>
      );
    }

    if (!recommendations || recommendations.length === 0) {
      if (recommendationsError) {
        return <Alert severity="error">Unable to load similar games right now.</Alert>;
      }

      if (!recommendationsAvailable) {
        return (
          <Alert severity="warning">
            Recommendations are temporarily unavailable while recommendation artifacts
            are missing or invalid. The rest of the app is still available.
          </Alert>
        );
      }

      return (
        <Typography variant="body2" color="text.secondary">
          No similar games matched this title.
        </Typography>
      );
    }

    return (
      <Grid container spacing={3}>
        {recommendations.map((rec) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={rec.id}>
            <GameCard
              game={rec}
              onClick={() => handleRecommendationClick(rec)}
              sortBy="rank"
              compact={true}
              isLibraryGame={libraryGameIdSet.has(rec.id)}
            />
          </Grid>
        ))}
      </Grid>
    );
  };

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth="md"
        fullWidth
        scroll="paper"
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
            {game.image && (
              <Box
                component="img"
                src={detailImageSrc}
                alt={game.name}
                sx={{
                  width: 100,
                  height: { xs: 120, sm: 140 }, // Responsive height constraint
                  objectFit: 'contain',
                  backgroundColor: bgColor,
                  transition: 'background-color 0.3s ease',
                  flexShrink: 0
                }}
                onLoad={handleImageLoad}
                onError={(event) => {
                  setImageCandidateIndex((previous) => {
                    const next = previous + 1;
                    if (next >= detailImageCandidates.length) {
                      event.currentTarget.src = placeholderImagePath;
                      return previous;
                    }
                    return next;
                  });
                }}
              />
            )}
            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              <Typography variant="h5" sx={{ mb: 1 }}>{game.name}</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Tooltip title={likedGames.some(g => g.id === game.id) ? 'Unlike' : 'Like'}>
                  <IconButton onClick={handleLikeClick} size="small">
                    {likedGames.some(g => g.id === game.id) ? <ThumbUpIcon color="success" /> : <ThumbUpOutlinedIcon />}
                  </IconButton>
                </Tooltip>
                <Tooltip title={dislikedGames.some(g => g.id === game.id) ? 'Remove dislike' : 'Dislike'}>
                  <IconButton onClick={handleDislikeClick} size="small">
                    {dislikedGames.some(g => g.id === game.id) ? <ThumbDownIcon color="error" /> : <ThumbDownOutlinedIcon />}
                  </IconButton>
                </Tooltip>
                {isLibraryGame && (
                  <Tooltip
                    title={
                      game.avg_box_volume && game.avg_box_volume <= 100
                        ? 'Available in Library, small games section'
                        : 'Available in Library'
                    }
                  >
                    <IconButton size="small" aria-label="Available in Library">
                      <MenuBookIcon color="primary" />
                      {game.avg_box_volume && game.avg_box_volume <= 100 && (
                        <EmergencyIcon
                          sx={{
                            position: 'absolute',
                            top: -3,
                            right: -3,
                            fontSize: '1rem',
                            color: 'primary.main',
                          }}
                        />
                      )}
                    </IconButton>
                  </Tooltip>
                )}
              </Box>
              
              {/* Game Statistics */}
              <Box sx={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', 
                gap: { xs: 0.75, sm: 1.5 }, // Smaller gap on mobile (xs), normal gap on larger screens
                alignItems: 'center'
              }}>
                {/* Players - 1st (matches GameCard order) */}
                <Tooltip title="Player Count">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <PeopleIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        {game.min_players === game.max_players
                          ? `${game.min_players} players`
                          : `${game.min_players}-${game.max_players} players`}
                      </Typography>
                      {playerCountSummary.best.length > 0 && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                          {`Best: ${playerCountSummary.best.join(', ')}`}
                        </Typography>
                      )}
                      {playerCountSummary.recommended.length > 0 && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                          {`Rec: ${playerCountSummary.recommended.join(', ')}`}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                </Tooltip>
                
                {/* Play Time - 2nd (matches GameCard order) */}
                <Tooltip title="Play Time">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <AccessTimeIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                    <Typography variant="body2" color="text.secondary">
                      {game.min_playtime === game.max_playtime
                        ? `${game.min_playtime} min`
                        : `${game.min_playtime}-${game.max_playtime} min`}
                    </Typography>
                  </Box>
                </Tooltip>
                
                {/* Complexity - 3rd (matches GameCard order) */}
                <Tooltip title="Game Weight (Complexity)">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <PsychologyAltOutlinedIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                    <Typography variant="body2" color="text.secondary">
                      {game.average_weight ? `${game.average_weight.toFixed(1)}/5` : 'N/A'}
                    </Typography>
                  </Box>
                </Tooltip>
                
                {/* Rating - 4th (matches GameCard order) - Hidden on mobile */}
                <Tooltip title="Average Rating">
                  <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 0.5 }}>
                    <StarBorderOutlinedIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                    <Typography variant="body2" color="text.secondary">
                      {game.average ? `${game.average.toFixed(1)}/10` : 'N/A'}
                    </Typography>
                  </Box>
                </Tooltip>
                
                {/* Additional fields after core GameCard info */}
                {/* Age - Hidden on mobile */}
                {game.min_age && (
                  <Tooltip title="Minimum Age">
                    <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 0.5 }}>
                      <ChildCareIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                      <Typography variant="body2" color="text.secondary">
                        {game.min_age}+
                      </Typography>
                    </Box>
                  </Tooltip>
                )}
                
                {/* Year Published */}
                {game.year_published && (
                  <Tooltip title="Year Published">
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <CalendarTodayIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                      <Typography variant="body2" color="text.secondary">
                        {game.year_published}
                      </Typography>
                    </Box>
                  </Tooltip>
                )}
                
                {/* BGG Rank - Hidden on mobile */}
                {game.rank && game.rank > 0 && (
                  <Tooltip title="BoardGameGeek Rank">
                    <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 0.5 }}>
                      <TrendingUpIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                      <Typography variant="body2" color="text.secondary">
                        #{game.rank}
                      </Typography>
                    </Box>
                  </Tooltip>
                )}
              </Box>
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, md: 6 }}>
              {renderList(game.designers, 'Designers', 'designer')}
              {renderList(game.artists, 'Artists', 'artist')}
              {renderList(game.mechanics, 'Mechanics', 'mechanic')}
              {renderList(game.categories, 'Categories', 'category')}
              {renderList(game.publishers, 'Publishers', 'publisher')}
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="subtitle1" gutterBottom>
                Description
              </Typography>
              <Typography 
                variant="body1" 
                sx={{ 
                  whiteSpace: 'pre-line',
                  mb: 2
                }}
              >
                {decodeGameDescription(game.description)}
              </Typography>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle1" gutterBottom>
                Similar Games
              </Typography>
              {renderRecommendations()}
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default GameDetails; 
