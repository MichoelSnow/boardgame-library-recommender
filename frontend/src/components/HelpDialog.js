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

const HelpDialog = ({ open, onClose, onStartTour, libraryName = '' }) => {
  const [expanded, setExpanded] = useState('getting-started');
  const libraryNamePrefix = libraryName ? `${libraryName} ` : '';

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
        <Typography variant="h5" component="div">
          {libraryNamePrefix}Board Game Catalog Help Guide
        </Typography>
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
                Welcome to the {libraryNamePrefix}Board Game Library! This tool helps
                you discover board games available at the convention and get
                personalized recommendations.
              </Typography>
              <Typography variant="subtitle2" gutterBottom>Quick Overview:</Typography>
              <List dense>
                <ListItem>
                  <ListItemText primary="Browse thousands of board games with detailed information" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Filter games by players, complexity, play time, age, style, game type, theme, and more" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Use Sort and Filters to organize and narrow the catalog" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Rate games and get recommendations based on your preferences" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Start with library games or include all board games" />
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
                    secondary="Select the search icon to open the field. The X clears entered text; when the field is empty, it closes the search."
                  />
                </ListItem>
                <ListItem>
                  <PeopleIcon sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText 
                    primary="Filters drawer"
                    secondary="Open Filters to choose players and requirements, Game Type, and Theme & Setting. Close the drawer to apply your selections."
                  />
                </ListItem>
                <ListItem>
                  <SortIcon sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText 
                    primary="Sort Options" 
                    secondary="Use Sort to order the catalog by rank, name, or another available ranking"
                  />
                </ListItem>
                <ListItem>
                  <ConstructionIcon sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText 
                    primary="Game Type"
                    secondary="Select one or more types. Multiple selections match games with any selected type."
                  />
                </ListItem>
                <ListItem>
                  <CategoryIcon sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText 
                    primary="Theme & Setting"
                    secondary="Select one or more themes or settings. Multiple selections match games with any selected option."
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Active Filters"
                    secondary="The drawer lists every active filter as a removable chip. The catalog shows up to three chips; select +N more to open the drawer."
                  />
                </ListItem>
              </List>
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="subtitle2" gutterBottom>Library Games Filter:</Typography>
              <Typography paragraph>
                By default, the catalog shows only {libraryNamePrefix}library games.
                Use the "All Board Games" toggle to include non-library games for
                recommendations and information. Games in the {libraryNamePrefix}
                library are marked with a <MenuBookIcon sx={{ fontSize: '1rem', verticalAlign: 'middle', mx: 0.25, color: 'primary.main' }} /> icon.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>Complexity Levels:</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                <Chip label="Light (< 2)" size="small" />
                <Chip label="Medium (2–4)" size="small" />
                <Chip label="Heavy (> 4)" size="small" />
              </Box>
              <Typography variant="body2" color="text.secondary" paragraph>
                Multiple complexity levels match any selected level. Other Group &amp; Requirements filters narrow results together: player count, maximum play time, minimum age, game style, and cooperative games.
              </Typography>
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="subtitle2" gutterBottom>Library Game Indicators:</Typography>
              <Typography paragraph>
                Games available in the {libraryNamePrefix}library are marked with a <MenuBookIcon sx={{ fontSize: '1rem', verticalAlign: 'middle', mx: 0.25, color: 'primary.main' }} /> icon 
                on each game card. When you toggle to "All Board Games", games without this icon are not available 
                at the convention but are included for recommendation purposes.
              </Typography>
              <Typography paragraph>
                Small games are marked with a <MenuBookIcon sx={{ fontSize: '1rem', verticalAlign: 'middle', color: 'primary.main' }} />
                <EmergencyIcon sx={{ fontSize: '0.7rem', verticalAlign: 'top', color: 'primary.main', ml: -0.5 }} /> 
                combined icon. These games are available in the special small games section of the library.
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
              <Typography paragraph>
                Recommendations use the hybrid recommender by default. Admins can tune
                hybrid weights in Admin Panel settings for all users.
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
                  <ListItemText primary="✓ All Board Games toggle" secondary="Filters recommendations between library games and all games" />
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
                Click on any game card to view detailed information including description, game types,
                themes, settings, designers, artists, and similar games.
              </Typography>
              
              <Typography variant="subtitle2" gutterBottom>Interactive Filtering:</Typography>
              <Typography paragraph>
                Filterable tags are marked as clickable. Selecting one closes the details view, returns to
                the game list, and applies that filter while preserving your other selections.
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText 
                    primary="Designers, Artists, Game Types, Themes and Settings"
                    secondary="Select a tag to apply its filter and return to the game list"
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
                <strong>Filter Integration:</strong> Detail filters are added to your existing selections.
                Use the Active Filters chips to review or remove them later.
              </Alert>
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
                Try searching with just part of the name, or turn on "All Board Games" if you're looking
                for games outside the convention library.
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
