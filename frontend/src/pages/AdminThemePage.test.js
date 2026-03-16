import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
    fetchThemeSettings.mockResolvedValue({ primary_color: '#D9272D' });
    updateThemeSettings.mockImplementation(async (primaryColor) => ({
      primary_color: primaryColor,
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
    await waitFor(() =>
      expect(screen.getByText('Current primary color: #D9272D')).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole('button', { name: '#007DBB' }));
    await waitFor(() =>
      expect(screen.getByText('Current primary color: #007DBB')).toBeInTheDocument()
    );
    expect(updateThemeSettings).toHaveBeenCalledWith('#007DBB');
  });

  test('warns when selected color fails AA contrast on white', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Current primary color: #D9272D')).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole('button', { name: '#F4B223' }));

    await waitFor(() =>
      expect(
        screen.getByText(/does not meet AA contrast on white/i)
      ).toBeInTheDocument()
    );
  });

  test('allows applying a custom hex theme color', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Current primary color: #D9272D')).toBeInTheDocument()
    );

    fireEvent.change(screen.getByLabelText('Custom hex color'), {
      target: { value: '#123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply Custom Color' }));

    await waitFor(() =>
      expect(screen.getByText('Current primary color: #123456')).toBeInTheDocument()
    );
    expect(updateThemeSettings).toHaveBeenCalledWith('#123456');
  });
});
