import React, { useMemo, useState } from 'react';
import { Box, Button, Card, CardContent, Chip, Stack, TextField, Typography } from '@mui/material';
import { useThemeSettings } from '../context/ThemeSettingsContext';
import { normalizeHexColor } from '../utils/colorContrast';

const AdminThemePage = () => {
  const {
    contrastRatioOnWhite,
    isPrimaryColorLimited,
    minAaContrastRatio,
    primaryColor,
    presetPrimaryColors,
    setPrimaryColor,
  } = useThemeSettings();
  const [customColor, setCustomColor] = useState(primaryColor);
  const [themeError, setThemeError] = useState('');
  const normalizedCustomColor = useMemo(
    () => normalizeHexColor(customColor),
    [customColor]
  );

  return (
    <Box sx={{ maxWidth: 720, mx: 'auto', mt: 4, px: 2 }}>
      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h4" component="h1">
              Theme Color
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Current primary color: {primaryColor}
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
