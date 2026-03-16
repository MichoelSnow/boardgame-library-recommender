import { getBestTextColor, getContrastRatio, normalizeHexColor } from './colorContrast';

describe('color contrast utilities', () => {
  test('normalizes hex colors', () => {
    expect(normalizeHexColor('#abc')).toBe('#AABBCC');
    expect(normalizeHexColor('d9272d')).toBe('#D9272D');
    expect(normalizeHexColor('bad-value')).toBeNull();
  });

  test('computes contrast ratio between two colors', () => {
    expect(getContrastRatio('#000000', '#FFFFFF')).toBeCloseTo(21, 2);
    expect(getContrastRatio('#D9272D', '#FFFFFF')).toBeGreaterThan(4.5);
    expect(getContrastRatio('#F4B223', '#FFFFFF')).toBeLessThan(4.5);
  });

  test('selects best text color for a background', () => {
    expect(getBestTextColor('#F4B223')).toBe('#000000');
    expect(getBestTextColor('#D9272D')).toBe('#FFFFFF');
  });
});
