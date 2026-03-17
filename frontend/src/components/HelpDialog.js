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
import MenuBookIcon from '@mui/icons-material/MenuBook';
import EmergencyIcon from '@mui/icons-material/Emergency';

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
                Welcome to the Board Game Library! This tool helps you discover board games 
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
                  <ListItemText primary="Focus on games specifically available at Library" />
                </ListItem>
              </List>
              <Alert severity="info" sx={{ mt: 2 }}>
                <strong>Convention Tip:</strong> Your preferences persist while your browser session is active
                (including normal refresh). They reset when the session ends, which keeps shared-device use safe.
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
              
              <Typography variant="subtitle2" gutterBottom>Library Games Filter:</Typography>
              <Typography paragraph>
                By default, the catalog shows only Library library games. Use the "All Board Games" toggle to 
                include non-library games for recommendations and information. Games in the Library library are 
                marked with a <MenuBookIcon sx={{ fontSize: '1rem', verticalAlign: 'middle', mx: 0.25, color: 'primary.main' }} /> icon.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>Weight (Complexity) Levels:</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                <Chip label="Beginner Friendly (≤ 2.0)" size="small" />
                <Chip label="Midweight (2.0 - 4.0)" size="small" />
                <Chip label="Heavy (≥ 4.0)" size="small" />
              </Box>
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="subtitle2" gutterBottom>Library Game Indicators:</Typography>
              <Typography paragraph>
                Games available in the Library library are marked with a <MenuBookIcon sx={{ fontSize: '1rem', verticalAlign: 'middle', mx: 0.25, color: 'primary.main' }} /> icon 
                on each game card. When you toggle to "All Board Games", games without this icon are not available 
                at the convention but are included for recommendation purposes.
              </Typography>
              <Typography paragraph>
                Small games are marked with a <MenuBookIcon sx={{ fontSize: '1rem', verticalAlign: 'middle', color: 'primary.main' }} />
                <EmergencyIcon sx={{ fontSize: '0.7rem', verticalAlign: 'top', color: 'primary.main', ml: -0.5 }} /> 
                combined icon. These games are available in the special small games section of the Library library.
              </Typography>
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
              
              <Typography variant="subtitle2" gutterBottom>Step 3: Refresh Your Recommendations (Simple!)</Typography>
              <Alert severity="info" sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>To update your recommendations with new preferences:</Typography>
                <List dense>
                  <ListItem sx={{ pl: 0 }}>
                    <ListItemText 
                      primary="1. Continue liking/disliking games (this automatically enables the refresh button)"
                    />
                  </ListItem>
                  <ListItem sx={{ pl: 0 }}>
                    <ListItemText 
                      primary="2. Click 'Refresh Recommendations' when you're ready for updated recommendations"
                    />
                  </ListItem>
                </List>
              </Alert>
              
              <Typography variant="subtitle2" gutterBottom>Step 4: Toggle Between Views</Typography>
              <Typography paragraph>
                Use the "Show Recommendations" toggle switch to easily switch between viewing 
                only your recommended games or browsing the full game library. Your recommendations 
                stay saved while you explore!
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>What Works in Recommendation Mode:</Typography>
              <List dense>
                <ListItem>
                  <ListItemText primary="✓ Liking and disliking games" secondary="Automatically enables 'Refresh Recommendations' button" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="✓ Viewing game details" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="✓ All Board Games toggle" secondary="Filters recommendations between Library library and all games" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="✓ Show Recommendations toggle" secondary="Switch between recommendation view and full library" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="✓ Pagination through recommendations" />
                </ListItem>
              </List>
              
              <Typography variant="subtitle2" gutterBottom>What's Different in Recommendation Mode:</Typography>
              <List dense>
                <ListItem>
                  <ListItemText primary="• Search and most filters" secondary="Only work when 'Show Recommendations' toggle is OFF (browsing full library)" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="• Sort options" secondary="Recommendations are automatically sorted by relevance" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="• Easy view switching" secondary="Toggle between recommendations and full library without losing your recommendations" />
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
                    secondary="These are marked as 'filterable' and clicking them will apply that filter to the main game list while keeping the dialog open"
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
                Your preferences (liked/disliked games) are session-scoped and reset when the session ends:
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText primary="• Close the browser tab" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="• Close the browser/app session on the shared device" />
                </ListItem>
              </List>
              
              <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>Quick Start for Convention Guests:</Typography>
              <List dense>
                <ListItem>
                  <ListItemText 
                    primary={<>1. Browse Library library games (default view) - look for the <MenuBookIcon sx={{ fontSize: '1rem', verticalAlign: 'middle', mx: 0.25, color: 'primary.main' }} /> icon (with <EmergencyIcon sx={{ fontSize: '0.7rem', verticalAlign: 'top', color: 'primary.main', ml: -0.5 }} /> for small games)</>}
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
                When you like/dislike more games, the "Refresh Recommendations" button becomes enabled. 
                Click it to get updated recommendations based on your new preferences.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>
                "The search and filters aren't working"
              </Typography>
              <Typography paragraph>
                You're viewing recommendations with the "Show Recommendations" toggle turned ON. 
                Turn the toggle OFF to browse the full library where all search and filters work normally.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>
                "How do I switch between recommendations and the full library?"
              </Typography>
              <Typography paragraph>
                Use the "Show Recommendations" toggle switch that appears after you get your first recommendations. 
                Toggle it ON to see only recommended games, or OFF to browse the full library with all filters available.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>
                "I can't find a specific game"
              </Typography>
              <Typography paragraph>
                Try searching with just part of the name, or turn off the "Library Games Only" filter 
                if you're looking for games not at the convention.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>
                "My preferences disappeared"
              </Typography>
              <Typography paragraph>
                This is normal when the session ends (for example browser/app session restart on a shared device).
                Regular page refresh should keep your current session preferences.
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
