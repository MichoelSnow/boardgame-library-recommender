import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  Chip,
  Divider,
  Alert,
  Stack,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import ThumbDownIcon from '@mui/icons-material/ThumbDown';
import SearchIcon from '@mui/icons-material/Search';
import PeopleIcon from '@mui/icons-material/People';
import ConstructionIcon from '@mui/icons-material/Construction';
import CategoryIcon from '@mui/icons-material/Category';
import SortIcon from '@mui/icons-material/Sort';

const HelpDialog = ({ open, onClose, onStartTour }) => {
  const [expanded, setExpanded] = useState('getting-started');

  const handleChange = (panel) => (event, isExpanded) => {
    setExpanded(isExpanded ? panel : false);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      scroll="paper"
    >
      <DialogTitle>
        <Typography variant="h5">Board Game Catalog Help Guide</Typography>
        <Typography variant="body2" color="text.secondary">
          Learn how to find and get recommendations for board games
        </Typography>
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={1}>
          {/* Getting Started */}
          <Accordion 
            expanded={expanded === 'getting-started'} 
            onChange={handleChange('getting-started')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Getting Started</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography paragraph>
                Welcome to the PAX TableTop Board Game Catalog! This tool helps you discover board games 
                available at the convention and get personalized recommendations.
              </Typography>
              <Typography variant="subtitle2" gutterBottom>Quick Overview:</Typography>
              <List dense>
                <ListItem>
                  <ListItemText primary="Browse thousands of board games with detailed information" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Filter games by player count, complexity, mechanics, and more" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Get recommendations based on your preferences" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Focus on games specifically available at PAX" />
                </ListItem>
              </List>
              <Alert severity="info" sx={{ mt: 2 }}>
                <strong>Convention Tip:</strong> Your preferences are session-based and will reset when 
                you refresh the page or close your browser. This makes it perfect for sharing devices 
                at the convention!
              </Alert>
            </AccordionDetails>
          </Accordion>

          {/* Finding Games */}
          <Accordion 
            expanded={expanded === 'finding-games'} 
            onChange={handleChange('finding-games')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Finding Games</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="subtitle2" gutterBottom>Search and Filters:</Typography>
              <List dense>
                <ListItem>
                  <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText 
                    primary="Search by game name" 
                    secondary="Type any part of a game's name to find it quickly"
                  />
                </ListItem>
                <ListItem>
                  <PeopleIcon sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText 
                    primary="Player Count Filter" 
                    secondary="Choose how many players, plus whether that count is 'Allowed', 'Recommended', or 'Best'"
                  />
                </ListItem>
                <ListItem>
                  <SortIcon sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText 
                    primary="Sort Options" 
                    secondary="Sort by overall rank, category ranks, or alphabetically"
                  />
                </ListItem>
                <ListItem>
                  <ConstructionIcon sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText 
                    primary="Game Mechanics" 
                    secondary="Filter by gameplay mechanics like 'Worker Placement' or 'Deck Building'"
                  />
                </ListItem>
                <ListItem>
                  <CategoryIcon sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText 
                    primary="Game Categories" 
                    secondary="Filter by themes like 'Fantasy', 'Economic', or 'Abstract Strategy'"
                  />
                </ListItem>
              </List>
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="subtitle2" gutterBottom>PAX Games Toggle:</Typography>
              <Typography paragraph>
                Use the "PAX Games Only" toggle to focus exclusively on games available at the convention. 
                This is especially useful when you want to try games you can actually play here!
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>Weight (Complexity) Levels:</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                <Chip label="Beginner Friendly (≤ 2.0)" size="small" />
                <Chip label="Midweight (2.0 - 4.0)" size="small" />
                <Chip label="Heavy Cardboard (≥ 4.0)" size="small" />
              </Box>
            </AccordionDetails>
          </Accordion>

          {/* Recommendations - The Complex Part */}
          <Accordion 
            expanded={expanded === 'recommendations'} 
            onChange={handleChange('recommendations')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Getting Recommendations (Important!)</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Alert severity="warning" sx={{ mb: 2 }}>
                <strong>Key Point:</strong> The recommendation workflow has specific steps that aren't obvious. 
                Please read this section carefully!
              </Alert>
              
              <Typography variant="subtitle2" gutterBottom>Step 1: Like and Dislike Games</Typography>
              <Typography paragraph>
                Browse games and use the thumbs up <ThumbUpIcon sx={{ fontSize: 'inherit', color: 'success.main' }} /> and 
                thumbs down <ThumbDownIcon sx={{ fontSize: 'inherit', color: 'error.main' }} /> buttons on game cards to 
                indicate your preferences. You need at least one liked or disliked game to get recommendations.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>Step 2: Generate Initial Recommendations</Typography>
              <Typography paragraph>
                Click the "Recommend Games" button to get your initial recommendations based on 
                your liked and disliked games.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>Step 3: Refine Your Recommendations (The Tricky Part!)</Typography>
              <Alert severity="info" sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>If you want to update your recommendations:</Typography>
                <List dense>
                  <ListItem sx={{ pl: 0 }}>
                    <ListItemText 
                      primary="1. While viewing recommendations, continue liking/disliking games"
                    />
                  </ListItem>
                  <ListItem sx={{ pl: 0 }}>
                    <ListItemText 
                      primary="2. Click 'Show All Games' to return to the main catalog"
                    />
                  </ListItem>
                  <ListItem sx={{ pl: 0 }}>
                    <ListItemText 
                      primary="3. Click 'Recommend Games' again to get updated recommendations"
                    />
                  </ListItem>
                </List>
              </Alert>
              
              <Typography variant="subtitle2" gutterBottom>What Works in Recommendation Mode:</Typography>
              <List dense>
                <ListItem>
                  <ListItemText primary="✓ Liking and disliking games" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="✓ Viewing game details" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="✓ PAX Games Only toggle" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="✓ Pagination through recommendations" />
                </ListItem>
              </List>
              
              <Typography variant="subtitle2" gutterBottom>What Doesn't Work in Recommendation Mode:</Typography>
              <List dense>
                <ListItem>
                  <ListItemText primary="✗ Search" secondary="Disabled while viewing recommendations" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="✗ Most filters" secondary="Sort, player count, mechanics, etc." />
                </ListItem>
                <ListItem>
                  <ListItemText primary="✗ Automatic recommendation updates" secondary="Must manually refresh as described above" />
                </ListItem>
              </List>
            </AccordionDetails>
          </Accordion>

          {/* Game Details */}
          <Accordion 
            expanded={expanded === 'game-details'} 
            onChange={handleChange('game-details')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Game Details & Smart Filtering</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography paragraph>
                Click on any game card to view detailed information including description, mechanics, 
                categories, designers, and similar games.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>Interactive Filtering:</Typography>
              <Typography paragraph>
                In the game details dialog, you can click on:
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText 
                    primary="Designers, Artists, Mechanics, Categories" 
                    secondary="These are marked as 'filterable' and clicking them will close the dialog and apply that filter to the main game list"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Publishers" 
                    secondary="These are not filterable (no click action)"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Similar Games" 
                    secondary="Click these to view details of recommended similar games"
                  />
                </ListItem>
              </List>
              
              <Alert severity="info" sx={{ mt: 2 }}>
                <strong>Filter Integration:</strong> When you click a filterable element (like a game mechanic), 
                it immediately applies that filter to your main game list. This is a quick way to find 
                more games with similar characteristics!
              </Alert>
            </AccordionDetails>
          </Accordion>

          {/* Convention Usage */}
          <Accordion 
            expanded={expanded === 'convention-usage'} 
            onChange={handleChange('convention-usage')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Convention Usage Tips</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="subtitle2" gutterBottom>Sharing Devices:</Typography>
              <Typography paragraph>
                This system is designed for convention use where multiple people share devices. 
                Your preferences (liked/disliked games) are temporary and reset when you:
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText primary="• Refresh the page" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="• Close the browser tab" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="• Navigate away and come back" />
                </ListItem>
              </List>
              
              <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>Quick Start for Convention Guests:</Typography>
              <List dense>
                <ListItem>
                  <ListItemText 
                    primary="1. Turn on 'PAX Games Only' to focus on available games"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="2. Use player count filter for your group size"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="3. Like/dislike a few games you recognize"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="4. Get recommendations to discover new games!"
                  />
                </ListItem>
              </List>
              
              <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>Mobile-Friendly:</Typography>
              <Typography>
                The interface is optimized for tablets and phones commonly used at conventions. 
                All features work on mobile devices.
              </Typography>
            </AccordionDetails>
          </Accordion>

          {/* Common Issues */}
          <Accordion 
            expanded={expanded === 'common-issues'} 
            onChange={handleChange('common-issues')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Common Questions</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="subtitle2" gutterBottom>
                "I liked more games but my recommendations didn't change"
              </Typography>
              <Typography paragraph>
                You need to click "Show All Games" then "Recommend Games" again. 
                The system doesn't automatically update recommendations.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>
                "The search and filters aren't working"
              </Typography>
              <Typography paragraph>
                You're probably in recommendation mode. Click "Show All Games" to return to the 
                main catalog where all filters work.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>
                "I can't find a specific game"
              </Typography>
              <Typography paragraph>
                Try searching with just part of the name, or turn off the "PAX Games Only" filter 
                if you're looking for games not at the convention.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>
                "My preferences disappeared"
              </Typography>
              <Typography paragraph>
                This is normal! The system resets when you refresh or navigate away. 
                It's designed for sharing devices at conventions.
              </Typography>
            </AccordionDetails>
          </Accordion>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>
          Close
        </Button>
        {onStartTour && (
          <Button 
            onClick={() => {
              onClose();
              onStartTour();
            }} 
            variant="contained"
          >
            Start Interactive Tour
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default HelpDialog;