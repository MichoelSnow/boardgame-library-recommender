import React, { useState } from 'react';
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
import PeopleIcon from '@mui/icons-material/People';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PsychologyAltOutlinedIcon from '@mui/icons-material/PsychologyAltOutlined';
import StarBorderOutlinedIcon from '@mui/icons-material/StarBorderOutlined';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ChildCareIcon from '@mui/icons-material/ChildCare';
import { placeholderImagePath } from '../config';
import { resolveGameDetailImageUrl } from '../utils/imageUrls';
import { useGameRecommendationsQuery } from '../hooks/useGameListQueries';

// Helper function to decode HTML entities and preserve line breaks
const decodeHtmlEntities = (text) => {
  if (!text) return '';
  const textarea = document.createElement('textarea');
  textarea.innerHTML = text;
  // Convert HTML line breaks to newlines and preserve them
  return textarea.value
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/&#10;/g, '\n')
    .replace(/&#13;/g, '\n')
    .replace(/&nbsp;/g, ' ');
};

const GameDetails = ({ game, open, onClose, onFilter, likedGames, dislikedGames, onLike, onDislike }) => {
  const [bgColor, setBgColor] = useState('#f5f5f5');
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

  // Handle image load to extract dominant color for background (same as GameCard)
  const handleImageLoad = (event) => {
    try {
      const img = event.target;
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);

      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      let r = 0, g = 0, b = 0;
      const total = imageData.length / 4;

      for (let i = 0; i < imageData.length; i += 4) {
        r += imageData[i];
        g += imageData[i + 1];
        b += imageData[i + 2];
      }

      r = Math.floor(r / total);
      g = Math.floor(g / total);
      b = Math.floor(b / total);

      const lighten = (color) => Math.min(255, Math.floor(color * 1.2));
      setBgColor(`rgba(${lighten(r)}, ${lighten(g)}, ${lighten(b)}, 0.3)`);
    } catch (error) {
      // Cross-origin images without CORS headers cannot be sampled.
      setBgColor('#f5f5f5');
    }
  };

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
    onClose();
    onFilter('game', rec.id, rec.name);
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
            
            return (
              <Tooltip 
                key={id}
                title={isClickable ? `Click to filter by ${name}` : name}
                placement="top"
              >
                <Chip
                  label={name}
                  size="small"
                  onClick={isClickable ? () => {
                    onFilter(type, id, name);
                    onClose();
                  } : undefined}
                  sx={isClickable ? {
                    cursor: 'pointer',
                    '&:hover': {
                      backgroundColor: 'action.hover'
                    }
                  } : undefined}
                />
              </Tooltip>
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
                src={resolveGameDetailImageUrl({
                  gameId: game.id,
                  imageUrl: game.image,
                })}
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
                  event.currentTarget.src = placeholderImagePath;
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
                    <Typography variant="body2" color="text.secondary">
                      {game.min_players === game.max_players
                        ? `${game.min_players} players`
                        : `${game.min_players}-${game.max_players} players`}
                    </Typography>
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
                {decodeHtmlEntities(game.description)}
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
