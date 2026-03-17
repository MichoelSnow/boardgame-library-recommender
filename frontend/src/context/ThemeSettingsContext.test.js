import { normalizeHexColor } from '../utils/colorContrast';

describe('ThemeSettingsContext helpers', () => {
  test('normalizeHexColor normalizes valid 6-char hex colors', () => {
    expect(normalizeHexColor('#d9272d')).toBe('#D9272D');
    expect(normalizeHexColor('007dbb')).toBe('#007DBB');
  });

  test('normalizeHexColor expands valid 3-char hex colors', () => {
    expect(normalizeHexColor('#abc')).toBe('#AABBCC');
  });

  test('normalizeHexColor rejects invalid values', () => {
    expect(normalizeHexColor('not-a-color')).toBeNull();
    expect(normalizeHexColor('#12')).toBeNull();
  });
});
