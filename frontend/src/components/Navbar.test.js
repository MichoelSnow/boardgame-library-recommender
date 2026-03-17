import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Navbar from './Navbar';
import AuthContext from '../context/AuthContext';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

jest.mock('./HelpDialog', () => () => null);
jest.mock('./GuidedTour', () => () => null);
jest.mock('./SuggestionsModal', () => () => null);
jest.mock('./PasswordChangeModal', () => () => null);
jest.mock('../context/ThemeSettingsContext', () => ({
  useThemeSettings: () => ({
    navbarTextColor: '#FFFFFF',
    primaryColor: '#D9272D',
  }),
}));

const renderNavbar = (authValue) =>
  render(
    <MemoryRouter>
      <AuthContext.Provider value={authValue}>
        <Navbar />
      </AuthContext.Provider>
    </MemoryRouter>
  );

describe('Navbar admin navigation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('shows Admin Panel button for admin users', () => {
    renderNavbar({
      user: { username: 'admin', is_admin: true, is_guest: false },
      logout: jest.fn(),
    });

    expect(screen.getByText('Admin Panel')).toBeInTheDocument();
  });

  test('does not show Admin Panel button for non-admin users', () => {
    renderNavbar({
      user: { username: 'user', is_admin: false, is_guest: false },
      logout: jest.fn(),
    });

    expect(screen.queryByText('Admin Panel')).not.toBeInTheDocument();
  });

  test('navigates to /admin when admin button is clicked', () => {
    renderNavbar({
      user: { username: 'admin', is_admin: true, is_guest: false },
      logout: jest.fn(),
    });

    fireEvent.click(screen.getByText('Admin Panel'));
    expect(mockNavigate).toHaveBeenCalledWith('/admin');
  });
});
