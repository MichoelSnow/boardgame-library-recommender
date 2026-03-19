import React, { useState, memo, useEffect, useRef } from 'react';
import {
  Card,
  CardContent,
  CardMedia,
  Typography,
  Box,
  IconButton,
  Tooltip,
} from '@mui/material';
import PeopleIcon from '@mui/icons-material/People';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PsychologyAltOutlinedIcon from '@mui/icons-material/PsychologyAltOutlined';
import StarBorderOutlinedIcon from '@mui/icons-material/StarBorderOutlined';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import ThumbDownIcon from '@mui/icons-material/ThumbDown';
import ThumbUpOutlinedIcon from '@mui/icons-material/ThumbUpOutlined';
import ThumbDownOutlinedIcon from '@mui/icons-material/ThumbDownOutlined';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import EmergencyIcon from '@mui/icons-material/Emergency';
import { placeholderImagePath } from '../config';
import { buildGameImageCandidates } from '../utils/imageUrls';

const DEFAULT_IMAGE_BG_COLOR = '#f5f5f5';

const extractAccentColor = (img) => {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx || !img?.width || !img?.height) {
    return DEFAULT_IMAGE_BG_COLOR;
  }

  canvas.width = img.width;
  canvas.height = img.height;
  ctx.drawImage(img, 0, 0);

  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  let r = 0;
  let g = 0;
  let b = 0;
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
  return `rgba(${lighten(r)}, ${lighten(g)}, ${lighten(b)}, 0.3)`;
};

const GameCard = memo(({
  game,
  onClick,
  sortBy,
  liked,
  disliked,
  onLike,
  onDislike,
  compact = false,
  isLibraryGame = false,
  enableImageAccent = true,
}) => {
  const [bgColor, setBgColor] = useState(DEFAULT_IMAGE_BG_COLOR);
  const accentJobRef = useRef(null);

  const imageCandidates = buildGameImageCandidates({
    gameId: game?.id,
    imageUrl: game?.image,
  });
  const [imageCandidateIndex, setImageCandidateIndex] = useState(0);
  const imageSrc = imageCandidates[imageCandidateIndex] || placeholderImagePath;

  const handleLikeClick = (e) => {
    e.stopPropagation();
    onLike();
  };

  const handleDislikeClick = (e) => {
    e.stopPropagation();
    onDislike();
  };

  useEffect(() => {
    if (!enableImageAccent) {
      setBgColor(DEFAULT_IMAGE_BG_COLOR);
    }
  }, [enableImageAccent]);

  useEffect(() => {
    setImageCandidateIndex(0);
  }, [game?.id, game?.image]);

  useEffect(() => () => {
    if (accentJobRef.current && window.cancelIdleCallback) {
      window.cancelIdleCallback(accentJobRef.current);
    } else if (accentJobRef.current) {
      window.clearTimeout(accentJobRef.current);
    }
  }, []);

  const handleImageLoad = (event) => {
    if (!enableImageAccent) {
      setBgColor(DEFAULT_IMAGE_BG_COLOR);
      return;
    }

    const img = event.currentTarget;
    const run = () => {
      try {
        setBgColor(extractAccentColor(img));
      } catch (error) {
        // Cross-origin images without CORS headers cannot be sampled.
        setBgColor(DEFAULT_IMAGE_BG_COLOR);
      }
    };

    if (accentJobRef.current && window.cancelIdleCallback) {
      window.cancelIdleCallback(accentJobRef.current);
    } else if (accentJobRef.current) {
      window.clearTimeout(accentJobRef.current);
    }

    if (window.requestIdleCallback) {
      accentJobRef.current = window.requestIdleCallback(run, { timeout: 500 });
    } else {
      accentJobRef.current = window.setTimeout(run, 0);
    }
  };

  const handleImageError = () => {
    setImageCandidateIndex((previous) => {
      if (previous >= imageCandidates.length) {
        return previous;
      }
      const next = previous + 1;
      return next;
    });
  };

  return (
    <Card 
      sx={{ 
        height: '100%',
        width: '100%',
        display: 'flex',
        flexDirection: 'row',
        justifyContent: 'space-between',
        '&:hover': {
          boxShadow: 6
        },
      }}
      data-tour="game-card"
    >
      <Box 
        onClick={onClick} 
        sx={{ 
          display: 'flex', 
          flexDirection: 'row', 
          flexGrow: 1, 
          textDecoration: 'none', 
          color: 'inherit', 
          cursor: 'pointer',
          minWidth: 0 // important for ellipsis
        }}
      >
        <CardMedia
          component="img"
          sx={{ 
            width: 120,
            height: 160,
            objectFit: 'contain',
            backgroundColor: bgColor,
            flexShrink: 0,
            alignSelf: 'center'
          }}
          image={imageSrc}
          alt={game.name}
          loading="lazy"
          onLoad={handleImageLoad}
          onError={handleImageError}
        />
        <CardContent sx={{ 
          flexGrow: 1, 
          p: 1, 
          display: 'flex', 
          flexDirection: 'column',
          minWidth: 0,
        }}>
          <Typography 
            variant="h4" 
            sx={{ 
              fontSize: '1.2rem', 
              mb: 0.5,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {game.name}
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
            <Tooltip title="Player Count" placement="top">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <PeopleIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                <Typography variant="body2" color="text.secondary">
                  {game.min_players === game.max_players
                    ? (compact ? game.min_players : `${game.min_players} players`)
                    : (compact ? `${game.min_players} - ${game.max_players}` : `${game.min_players} - ${game.max_players} players`)}
                </Typography>
              </Box>
            </Tooltip>
            <Tooltip title="Play Time" placement="top">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <AccessTimeIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                <Typography variant="body2" color="text.secondary">
                  {game.min_playtime === game.max_playtime
                    ? (compact ? game.min_playtime : `${game.min_playtime} min`)
                    : (compact ? `${game.min_playtime} - ${game.max_playtime}` : `${game.min_playtime} - ${game.max_playtime} min`)}
                </Typography>
              </Box>
            </Tooltip>
            <Tooltip title="Game Weight (Complexity)" placement="top">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <PsychologyAltOutlinedIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                <Typography variant="body2" color="text.secondary">
                  {game.average_weight ? `${game.average_weight.toFixed(1)}/5` : 'N/A'}
                </Typography>
              </Box>
            </Tooltip>
            <Tooltip title={sortBy === 'recommendation_score' ? 'Rating (Relevance)' : 'Average Rating'} placement="top">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <StarBorderOutlinedIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
                <Typography variant="body2" color="text.secondary">
                  {game.average ? game.average.toFixed(1) : 'N/A'}
                  {sortBy === 'recommendation_score' && game.recommendation_score && ` (${(game.recommendation_score * 100).toFixed(0)}%)`}
                </Typography>
              </Box>
            </Tooltip>
          </Box>
        </CardContent>
      </Box>
      <Box 
        sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-start', alignItems: 'center', p: 0.5, borderLeft: '1px solid', borderColor: 'divider' }}
        data-tour="like-buttons"
      >
        {isLibraryGame ? (
          <Tooltip title={game.avg_box_volume && game.avg_box_volume <= 100 ? 
            "Available in Library, small games section" : 
            "Available in Library"} 
            placement="left">
            <IconButton size="small" sx={{ mb: 2, cursor: 'default' }}>
              <MenuBookIcon color="primary" />
              {game.avg_box_volume && game.avg_box_volume <= 100 && 
                <EmergencyIcon sx={{ position: 'absolute', top: -3, right: -3, fontSize: '1rem', color: 'primary.main' }} />
              }
            </IconButton>
          </Tooltip>
        ) : (
          <IconButton size="small" disabled sx={{ mb: 2, visibility: 'hidden' }}>
            <MenuBookIcon />
          </IconButton>
        )}
        <Tooltip title={liked ? 'Unlike' : 'Like'} placement="left">
          <IconButton onClick={handleLikeClick} size="small">
            {liked ? <ThumbUpIcon color="success" /> : <ThumbUpOutlinedIcon />}
          </IconButton>
        </Tooltip>
        <Tooltip title={disliked ? 'Remove dislike' : 'Dislike'} placement="left">
          <IconButton onClick={handleDislikeClick} size="small">
            {disliked ? <ThumbDownIcon color="error" /> : <ThumbDownOutlinedIcon />}
          </IconButton>
        </Tooltip>
      </Box>
    </Card>
  );
});

export default GameCard; 
