import React, { useState, useEffect, useMemo } from 'react';
import {
  Backdrop,
  Paper,
  Typography,
  Button,
  Box,
  IconButton,
  Stack,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';

const buildTourSteps = (libraryName = '') => {
  const libraryNamePrefix = libraryName ? `${libraryName} ` : '';
  return [
    {
      id: 'welcome',
      title: `Welcome to the ${libraryNamePrefix}Board Game Catalog!`,
      content: 'This quick tour highlights the main ways to search, filter, browse, and get recommendations.',
      target: null,
      position: 'center',
    },
    {
      id: 'search',
      title: 'Search Games',
      content: 'Select the search icon to open the game-name search field. The single X clears the text when a search is entered and closes the field when it is empty.',
      target: '[data-tour="search-control"]',
      position: 'bottom',
    },
    {
      id: 'sort',
      title: 'Sort Games',
      content: 'Use Sort to change the order of the catalog. Your selected sort remains separate from filters and recommendations.',
      target: '[data-tour="sort-control"]',
      position: 'bottom',
    },
    {
      id: 'filters',
      title: 'Filter Games',
      content: 'Open Filters to choose players and requirements, Game Type, and Theme & Setting. Multiple choices within Game Type or Theme & Setting match any selected option; different filter groups narrow results together.',
      target: '[data-tour="filter-drawer"]',
      position: 'bottom',
    },
    {
      id: 'library-indicator',
      title: 'Library Game Indicator',
      content: 'Look for the book icon on game cards to see which games are available in the library. Games without this icon are outside the current library collection.',
      target: '[data-tour="game-card"]:first-child',
      position: 'top',
    },
    {
      id: 'library-toggle',
      title: 'All Board Games',
      content: `The catalog starts with ${libraryNamePrefix}library games. Turn on All Board Games to include games outside the collection for browsing and recommendations.`,
      target: '[data-tour="library-toggle"]',
      position: 'bottom',
    },
    {
      id: 'like-buttons',
      title: 'Like & Dislike Games',
      content: 'Use the thumbs up and thumbs down buttons to record your preferences. You can rate games even when they are outside the library.',
      target: '[data-tour="game-card"]:first-child',
      position: 'top',
    },
    {
      id: 'recommend-button',
      title: 'Get Recommendations',
      content: 'After rating at least one game, select Recommend Games to create recommendations based on your preferences.',
      target: '[data-tour="recommend-button"]',
      position: 'top',
    },
    {
      id: 'recommendation-workflow',
      title: 'Update Recommendations',
      content: 'After your first recommendations, rate more games and select Refresh Recommendations when you want an updated result.',
      target: '[data-tour="refresh-recommendations-button"]',
      position: 'top',
      important: true,
    },
    {
      id: 'show-recommendations-toggle',
      title: 'Show Recommendations',
      content: 'Use this toggle to switch between recommended games and the regular catalog. Your recommendations remain saved while you browse.',
      target: '[data-tour="show-recommendations-toggle"]',
      position: 'top',
    },
    {
      id: 'game-details',
      title: 'Game Details & Filtering',
      content: 'Select a game card for details. Filterable tags such as designers, artists, game types, themes and settings close the details view and apply that filter to the list.',
      target: '[data-tour="game-card"]:first-child',
      position: 'top',
    },
    {
      id: 'navigation-menu',
      title: 'More Help',
      content: 'Open the navigation menu and choose Help / Tour whenever you want to revisit these instructions. Your session preferences reset when the session ends.',
      target: '[data-tour="navigation-menu"]',
      position: 'bottom',
    },
  ];
};

const GuidedTour = ({ isOpen, onClose, currentMode = 'browse', libraryName = '' }) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [highlightedElement, setHighlightedElement] = useState(null);
  const tourSteps = useMemo(() => buildTourSteps(libraryName), [libraryName]);

  const isLastStep = currentStep >= tourSteps.length - 1;
  const isFirstStep = currentStep === 0;
  const step = tourSteps[currentStep];

  useEffect(() => {
    if (!isOpen) {
      setCurrentStep(0);
      setHighlightedElement(null);
      return;
    }

    const stepInfo = tourSteps[currentStep];
    if (stepInfo?.target) {
      const element = document.querySelector(stepInfo.target);
      setHighlightedElement(element || null);
      if (element) {
        // Scroll element into view
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } else {
      setHighlightedElement(null);
    }
  }, [isOpen, currentStep, tourSteps]);

  const handleNext = () => {
    if (isLastStep) {
      onClose();
    } else {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handlePrevious = () => {
    if (!isFirstStep) {
      setCurrentStep(prev => prev - 1);
    }
  };

  const handleSkip = () => {
    onClose();
  };

  const getTooltipPosition = () => {
    if (!highlightedElement || step.position === 'center') {
      return {
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 2000,
      };
    }

    const rect = highlightedElement.getBoundingClientRect();
    const tooltipWidth = 320;
    const tooltipHeight = 280; // Increased height for better content fit
    const margin = 20;

    let position = {
      position: 'fixed',
      zIndex: 2000,
    };

    switch (step.position) {
      case 'top':
        position.top = rect.top - tooltipHeight - margin;
        position.left = rect.left + (rect.width / 2) - (tooltipWidth / 2);
        break;
      case 'bottom':
        position.top = rect.bottom + margin;
        position.left = rect.left + (rect.width / 2) - (tooltipWidth / 2);
        break;
      case 'left':
        position.top = rect.top + (rect.height / 2) - (tooltipHeight / 2);
        position.left = rect.left - tooltipWidth - margin;
        break;
      case 'right':
        position.top = rect.top + (rect.height / 2) - (tooltipHeight / 2);
        position.left = rect.right + margin;
        break;
      default:
        position.top = '50%';
        position.left = '50%';
        position.transform = 'translate(-50%, -50%)';
    }

    // Smart positioning to avoid covering target element
    if (step.id === 'recommend-button') {
      // For recommend button, always position to the right side to avoid covering it
      position.top = rect.top + (rect.height / 2) - (tooltipHeight / 2);
      position.left = rect.right + margin * 2;
      
      // If no room on right, position to the left
      if (position.left + tooltipWidth > window.innerWidth - margin) {
        position.left = rect.left - tooltipWidth - margin * 2;
      }
      
      // If still no room (very narrow screen), position above with large margin
      if (position.left < margin) {
        position.top = rect.top - tooltipHeight - margin * 3;
        position.left = rect.left + (rect.width / 2) - (tooltipWidth / 2);
      }
    }

    // Keep tooltip on screen
    if (position.left < margin) position.left = margin;
    if (position.left + tooltipWidth > window.innerWidth - margin) {
      position.left = window.innerWidth - tooltipWidth - margin;
    }
    if (position.top < margin) position.top = margin;
    if (position.top + tooltipHeight > window.innerHeight - margin) {
      position.top = window.innerHeight - tooltipHeight - margin;
    }

    return position;
  };

  if (!isOpen) return null;

  return (
    <>
      <Backdrop
        open={isOpen}
        sx={{
          zIndex: 1500,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
        }}
        onClick={onClose}
      />
      
      {/* Highlight overlay for target element */}
      {highlightedElement && (
        <Box
          sx={{
            position: 'fixed',
            top: highlightedElement.getBoundingClientRect().top - 4,
            left: highlightedElement.getBoundingClientRect().left - 4,
            width: highlightedElement.getBoundingClientRect().width + 8,
            height: highlightedElement.getBoundingClientRect().height + 8,
            border: '3px solid #904799',
            borderRadius: 1,
            zIndex: 1600,
            pointerEvents: 'none',
            animation: 'pulse 2s infinite',
            '@keyframes pulse': {
              '0%': { opacity: 1 },
              '50%': { opacity: 0.5 },
              '100%': { opacity: 1 },
            },
          }}
        />
      )}

      {/* Tour tooltip */}
      <Paper
        elevation={8}
        sx={{
          ...getTooltipPosition(),
          width: 320,
          maxHeight: 400,
          overflow: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <Box sx={{ p: 2 }}>
          {/* Header */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
            <Typography 
              variant="h6" 
              sx={{ 
                color: step.important ? 'error.main' : 'primary.main',
                pr: 1 
              }}
            >
              {step.title}
            </Typography>
            <IconButton size="small" onClick={onClose}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>

          {/* Content */}
          <Typography variant="body2" sx={{ mb: 3, lineHeight: 1.5 }}>
            {step.content}
          </Typography>


          {/* Controls */}
          <Box>
            {/* Progress indicator and step counter */}
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', mb: 2, gap: 2 }}>
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                {tourSteps.map((_, index) => (
                  <Box
                    key={index}
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      backgroundColor: index === currentStep ? 'primary.main' : 'grey.300',
                    }}
                  />
                ))}
              </Box>
              <Typography variant="caption" color="text.secondary">
                {currentStep + 1} of {tourSteps.length}
              </Typography>
            </Box>
            
            {/* Navigation buttons */}
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Box sx={{ minWidth: 100 }}>
                {!isFirstStep && (
                  <Button
                    size="small"
                    startIcon={<ArrowBackIcon />}
                    onClick={handlePrevious}
                  >
                    Previous
                  </Button>
                )}
              </Box>

              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  onClick={handleSkip}
                  color="inherit"
                >
                  Skip Tour
                </Button>
                <Button
                  variant="contained"
                  size="small"
                  endIcon={!isLastStep && <ArrowForwardIcon />}
                  onClick={handleNext}
                >
                  {isLastStep ? 'Finish' : 'Next'}
                </Button>
              </Stack>
            </Stack>
          </Box>
        </Box>
      </Paper>
    </>
  );
};

export default GuidedTour;
