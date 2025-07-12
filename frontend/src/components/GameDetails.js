import React, { useState, useEffect } from 'react';
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
} from '@mui/material';
import axios from 'axios';
import GameCard from './GameCard';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import ThumbDownIcon from '@mui/icons-material/ThumbDown';
import ThumbUpOutlinedIcon from '@mui/icons-material/ThumbUpOutlined';
import ThumbDownOutlinedIcon from '@mui/icons-material/ThumbDownOutlined';
import { apiBaseUrl, imageBaseUrl } from '../config';

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
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedGame, setSelectedGame] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  // Get the appropriate image URL based on environment
  const getImageUrl = (imageUrl) => {
    if (!imageUrl) return null;
    
    // If imageBaseUrl is null, we're in production and should use proxy
    if (!imageBaseUrl) {
      return `${apiBaseUrl}/proxy-image/${encodeURIComponent(imageUrl)}`; // Use proxy to avoid CORS issues
    }
    
    // Otherwise, use the proxy through our backend
    return `${imageBaseUrl}/${imageUrl.split('/').pop()}`;
  };

  useEffect(() => {
    const fetchRecommendations = async () => {
      if (!game) return;
      setLoading(true);
      try {
        const response = await axios.get(`${apiBaseUrl}/recommendations/${game.id}`);
        setRecommendations(response.data);
      } catch (err) {
        console.error('Failed to fetch recommendations:', err);
      } finally {
        setLoading(false);
      }
    };

    if (open && game) {
      fetchRecommendations();
    }
  }, [game, open]);

  if (!game) return null;

  const handleLikeClick = (e) => {
    e.stopPropagation();
    onLike(game);
  };

  const handleDislikeClick = (e) => {
    e.stopPropagation();
    onDislike(game);
  };

  const handleRecommendationClick = async (rec) => {
    try {
      await axios.get(`${apiBaseUrl}/games/${rec.id}`);
      onClose();
      onFilter('game', rec.id, rec.name);
    } catch (err) {
      console.error('Failed to fetch recommended game:', err);
    }
  };

  const renderList = (items, label, type) => {
    if (!items || items.length === 0) return null;
    const isFilterable = type === 'designer' || type === 'artist' || type === 'mechanic' || type === 'category';

    return (
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          {label}{isFilterable && ' (filterable)'}
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
              <Chip
                key={id}
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
            );
          })}
        </Box>
      </Box>
    );
  };

  const renderRecommendations = () => {
    if (loading) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
          <CircularProgress />
        </Box>
      );
    }

    if (!recommendations || recommendations.length === 0) {
      return (
        <Typography variant="body2" color="text.secondary">
          No recommendations available.
        </Typography>
      );
    }

    return (
      <Grid container spacing={3}>
        {recommendations.map((rec) => (
          <Grid item xs={12} sm={6} md={4} key={rec.id}>
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
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {game.image && (
              <Box
                component="img"
                src={getImageUrl(game.image)} // Use proxy function instead of direct URL
                alt={game.name}
                sx={{
                  width: 100,
                  height: 100,
                  objectFit: 'contain',
                  backgroundColor: '#f5f5f5'
                }}
                crossOrigin="anonymous"
              />
            )}
            <Box>
              <Typography variant="h5">{game.name}</Typography>
              <Box>
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
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              {renderList(game.designers, 'Designers', 'designer')}
              {renderList(game.artists, 'Artists', 'artist')}
              {renderList(game.mechanics, 'Mechanics', 'mechanic')}
              {renderList(game.categories, 'Categories', 'category')}
              {renderList(game.publishers, 'Publishers', 'publisher')}
            </Grid>
            <Grid item xs={12} md={6}>
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
            <Grid item xs={12}>
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
      {selectedGame && (
        <GameDetails
          game={selectedGame}
          open={detailsOpen}
          onClose={() => {
            setDetailsOpen(false);
            setSelectedGame(null);
          }}
          onFilter={onFilter}
          likedGames={likedGames}
          dislikedGames={dislikedGames}
          onLike={onLike}
          onDislike={onDislike}
        />
      )}
    </>
  );
};

export default GameDetails; 