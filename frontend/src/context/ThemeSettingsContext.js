import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { fetchThemeSettings, updateThemeSettings } from '../api/theme';
import {
  getBestTextColor,
  getContrastRatio,
  normalizeHexColor,
} from '../utils/colorContrast';

export const PRESET_PRIMARY_COLORS = [
  '#904799',
  '#D9272D',
  '#007DBB',
  '#F4B223',
];

export const DEFAULT_PRIMARY_COLOR = '#D9272D';
export const MIN_AA_CONTRAST_RATIO = 4.5;
export const LOW_CONTRAST_FALLBACK_PRIMARY_COLOR = '#000000';
const THEME_REFRESH_INTERVAL_MS = 60 * 1000;

const ThemeSettingsContext = createContext();

function getInitialPrimaryColor() {
  return DEFAULT_PRIMARY_COLOR;
}

export function ThemeSettingsProvider({ children }) {
  const [primaryColor, setPrimaryColorState] = useState(getInitialPrimaryColor);

  useEffect(() => {
    let isMounted = true;

    const loadThemeSettings = async () => {
      try {
        const payload = await fetchThemeSettings();
        const normalized = normalizeHexColor(payload?.primary_color);
        if (isMounted && normalized) {
          setPrimaryColorState(normalized);
        }
      } catch (_error) {
        // Keep safe default when remote theme settings are unavailable.
      }
    };

    loadThemeSettings();
    const refreshTimer = window.setInterval(loadThemeSettings, THEME_REFRESH_INTERVAL_MS);

    return () => {
      isMounted = false;
      window.clearInterval(refreshTimer);
    };
  }, []);

  const setPrimaryColor = async (value) => {
    const normalized = normalizeHexColor(value);
    if (!normalized) {
      return false;
    }

    try {
      const payload = await updateThemeSettings(normalized);
      const persisted = normalizeHexColor(payload?.primary_color);
      setPrimaryColorState(persisted || normalized);
      return true;
    } catch (_error) {
      return false;
    }
  };

  const value = useMemo(
    () => {
      const contrastRatioOnWhite =
        getContrastRatio(primaryColor, '#FFFFFF') || MIN_AA_CONTRAST_RATIO;
      const isPrimaryColorLimited = contrastRatioOnWhite < MIN_AA_CONTRAST_RATIO;
      const effectivePrimaryColor = isPrimaryColorLimited
        ? LOW_CONTRAST_FALLBACK_PRIMARY_COLOR
        : primaryColor;
      const navbarTextColor = getBestTextColor(primaryColor);

      return {
        contrastRatioOnWhite,
        defaultPrimaryColor: DEFAULT_PRIMARY_COLOR,
        effectivePrimaryColor,
        isPrimaryColorLimited,
        minAaContrastRatio: MIN_AA_CONTRAST_RATIO,
        navbarTextColor,
        presetPrimaryColors: PRESET_PRIMARY_COLORS,
        primaryColor,
        setPrimaryColor,
      };
    },
    [primaryColor, setPrimaryColor]
  );

  return (
    <ThemeSettingsContext.Provider value={value}>
      {children}
    </ThemeSettingsContext.Provider>
  );
}

export function useThemeSettings() {
  const ctx = useContext(ThemeSettingsContext);
  if (!ctx) {
    throw new Error('useThemeSettings must be used within ThemeSettingsProvider');
  }
  return ctx;
}
