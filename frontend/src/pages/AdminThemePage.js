import React, { useEffect, useMemo, useState } from 'react';
import { Box, Button, Card, CardContent, Chip, Stack, TextField, Typography } from '@mui/material';
import { useThemeSettings } from '../context/ThemeSettingsContext';
import { normalizeHexColor } from '../utils/colorContrast';

const AdminThemePage = () => {
  const {
    collaborativeWeight,
    contrastRatioOnWhite,
    contentWeight,
    isPrimaryColorLimited,
    libraryName,
    minAaContrastRatio,
    primaryColor,
    presetPrimaryColors,
    qualityWeight,
    setRecommenderWeights,
    setLibraryName,
    setPrimaryColor,
  } = useThemeSettings();
  const [customColor, setCustomColor] = useState(primaryColor);
  const [nameInput, setNameInput] = useState(libraryName);
  const [collaborativeWeightInput, setCollaborativeWeightInput] = useState(
    collaborativeWeight.toFixed(2)
  );
  const [contentWeightInput, setContentWeightInput] = useState(contentWeight.toFixed(2));
  const [qualityWeightInput, setQualityWeightInput] = useState(qualityWeight.toFixed(2));
  const [themeError, setThemeError] = useState('');
  const normalizedCustomColor = useMemo(
    () => normalizeHexColor(customColor),
    [customColor]
  );

  useEffect(() => {
    setNameInput(libraryName);
  }, [libraryName]);

  useEffect(() => {
    setCollaborativeWeightInput(collaborativeWeight.toFixed(2));
  }, [collaborativeWeight]);

  useEffect(() => {
    setContentWeightInput(contentWeight.toFixed(2));
  }, [contentWeight]);

  useEffect(() => {
    setQualityWeightInput(qualityWeight.toFixed(2));
  }, [qualityWeight]);

  return (
    <Box sx={{ maxWidth: 720, mx: 'auto', mt: 4, px: 2 }}>
      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h4" component="h1">
              Theme, Library, and Recommender Settings
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Current primary color: {primaryColor}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Current library/convention name:{' '}
              {libraryName ? libraryName : '(not set)'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Current recommender weights: CF={collaborativeWeight.toFixed(2)}, Content=
              {contentWeight.toFixed(2)}, Quality={qualityWeight.toFixed(2)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Contrast on white: {contrastRatioOnWhite.toFixed(2)}:1 (AA target:{' '}
              {minAaContrastRatio}:1)
            </Typography>
            {isPrimaryColorLimited && (
              <Typography variant="body2" color="warning.main">
                This color does not meet AA contrast on white. It will be limited to
                high-contrast-safe areas like the navbar, and the rest of the app uses
                black (#000000) as fallback accent color.
              </Typography>
            )}
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {presetPrimaryColors.map((color) => (
                <Chip
                  key={color}
                  label={color}
                  onClick={async () => {
                    const ok = await setPrimaryColor(color);
                    if (!ok) {
                      setThemeError('Failed to save theme color.');
                      return;
                    }
                    setThemeError('');
                  }}
                  color={color === primaryColor ? 'primary' : 'default'}
                  variant={color === primaryColor ? 'filled' : 'outlined'}
                  sx={{
                    mb: 1,
                    borderColor: color,
                    backgroundColor: color === primaryColor ? color : 'transparent',
                    color: color === primaryColor ? '#fff' : 'text.primary',
                  }}
                />
              ))}
            </Stack>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <TextField
                label="Custom hex color"
                value={customColor}
                onChange={(event) => setCustomColor(event.target.value)}
                placeholder="#D9272D"
                size="small"
              />
              <TextField
                label="Pick color"
                type="color"
                value={normalizedCustomColor || '#000000'}
                onChange={(event) => setCustomColor(event.target.value)}
                size="small"
                sx={{ width: 120 }}
              />
              <Button
                variant="outlined"
                onClick={async () => {
                  if (normalizedCustomColor) {
                    const ok = await setPrimaryColor(normalizedCustomColor);
                    if (!ok) {
                      setThemeError('Failed to save theme color.');
                      return;
                    }
                    setThemeError('');
                  }
                }}
                disabled={!normalizedCustomColor}
              >
                Apply Custom Color
              </Button>
            </Stack>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <TextField
                label="Library / Convention Name"
                value={nameInput}
                onChange={(event) => setNameInput(event.target.value)}
                placeholder="Optional name prefix"
                size="small"
                inputProps={{ maxLength: 80 }}
                fullWidth
              />
              <Button
                variant="outlined"
                onClick={async () => {
                  const ok = await setLibraryName(nameInput);
                  if (!ok) {
                    setThemeError('Failed to save library/convention name.');
                    return;
                  }
                  setThemeError('');
                }}
              >
                Save Name
              </Button>
            </Stack>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <TextField
                label="Collaborative weight"
                value={collaborativeWeightInput}
                onChange={(event) => setCollaborativeWeightInput(event.target.value)}
                size="small"
                sx={{ minWidth: 170 }}
              />
              <TextField
                label="Content weight"
                value={contentWeightInput}
                onChange={(event) => setContentWeightInput(event.target.value)}
                size="small"
                sx={{ minWidth: 150 }}
              />
              <TextField
                label="Quality weight"
                value={qualityWeightInput}
                onChange={(event) => setQualityWeightInput(event.target.value)}
                size="small"
                sx={{ minWidth: 150 }}
              />
              <Button
                variant="outlined"
                onClick={async () => {
                  const nextCollaborativeWeight = Number.parseFloat(
                    collaborativeWeightInput
                  );
                  const nextContentWeight = Number.parseFloat(contentWeightInput);
                  const nextQualityWeight = Number.parseFloat(qualityWeightInput);
                  if (
                    !Number.isFinite(nextCollaborativeWeight) ||
                    !Number.isFinite(nextContentWeight) ||
                    !Number.isFinite(nextQualityWeight)
                  ) {
                    setThemeError('Recommender weights must be valid numbers.');
                    return;
                  }
                  if (
                    nextCollaborativeWeight < 0 ||
                    nextCollaborativeWeight > 1 ||
                    nextContentWeight < 0 ||
                    nextContentWeight > 1 ||
                    nextQualityWeight < 0 ||
                    nextQualityWeight > 1
                  ) {
                    setThemeError('Recommender weights must be between 0.00 and 1.00.');
                    return;
                  }
                  const ok = await setRecommenderWeights({
                    nextCollaborativeWeight,
                    nextContentWeight,
                    nextQualityWeight,
                  });
                  if (!ok) {
                    setThemeError('Failed to save recommender weights.');
                    return;
                  }
                  setThemeError('');
                }}
              >
                Save Weights
              </Button>
            </Stack>
            {themeError && (
              <Typography variant="body2" color="error">
                {themeError}
              </Typography>
            )}
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
};

export default AdminThemePage;
