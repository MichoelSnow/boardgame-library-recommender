import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeSettingsProvider } from '../context/ThemeSettingsContext';
import { fetchThemeSettings, updateThemeSettings } from '../api/theme';
import AdminThemePage from './AdminThemePage';

jest.mock('../api/theme', () => ({
  fetchThemeSettings: jest.fn(),
  updateThemeSettings: jest.fn(),
}));

describe('AdminThemePage', () => {
  beforeEach(() => {
    fetchThemeSettings.mockResolvedValue({
      primary_color: '#D9272D',
      library_name: null,
    });
    updateThemeSettings.mockImplementation(async ({ primaryColor, libraryName }) => ({
      primary_color: primaryColor || '#D9272D',
      library_name: libraryName?.trim() || null,
    }));
  });

  const renderPage = () =>
    render(
      <ThemeSettingsProvider>
        <MemoryRouter>
          <AdminThemePage />
        </MemoryRouter>
      </ThemeSettingsProvider>
    );

  test('allows selecting a preset theme color', async () => {
    renderPage();
    await screen.findByText('Current primary color: #D9272D');

    fireEvent.click(screen.getByRole('button', { name: '#007DBB' }));
    await screen.findByText('Current primary color: #007DBB');
    expect(updateThemeSettings).toHaveBeenCalledWith(
      expect.objectContaining({ primaryColor: '#007DBB' })
    );
  });

  test('warns when selected color fails AA contrast on white', async () => {
    renderPage();
    await screen.findByText('Current primary color: #D9272D');

    fireEvent.click(screen.getByRole('button', { name: '#F4B223' }));
    await screen.findByText(/does not meet AA contrast on white/i);
  });

  test('allows applying a custom hex theme color', async () => {
    renderPage();
    await screen.findByText('Current primary color: #D9272D');

    fireEvent.change(screen.getByLabelText('Custom hex color'), {
      target: { value: '#123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply Custom Color' }));

    await screen.findByText('Current primary color: #123456');
    expect(updateThemeSettings).toHaveBeenCalledWith(
      expect.objectContaining({ primaryColor: '#123456' })
    );
  });

  test('allows saving and clearing library/convention name', async () => {
    renderPage();
    await screen.findByText(/Current library\/convention name:/i);

    fireEvent.change(screen.getByLabelText('Library / Convention Name'), {
      target: { value: 'PAX East' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save Name' }));
    await screen.findByText('Current library/convention name: PAX East');

    fireEvent.change(screen.getByLabelText('Library / Convention Name'), {
      target: { value: '' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save Name' }));
    await screen.findByText('Current library/convention name: (not set)');
  });
});
