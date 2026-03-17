import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AdminRoute from './AdminRoute';
import AuthContext from '../context/AuthContext';

const renderWithAuth = (authValue) =>
  render(
    <MemoryRouter>
      <AuthContext.Provider value={authValue}>
        <AdminRoute>
          <div>Admin Content</div>
        </AdminRoute>
      </AuthContext.Provider>
    </MemoryRouter>,
  );

describe('AdminRoute', () => {
  test('renders children for admin users', () => {
    renderWithAuth({
      loading: false,
      user: { username: 'admin', is_admin: true },
    });

    expect(screen.getByText('Admin Content')).toBeInTheDocument();
  });

  test('shows access required message for non-admin users', () => {
    renderWithAuth({
      loading: false,
      user: { username: 'user', is_admin: false },
    });

    expect(screen.getByText('Admin Access Required')).toBeInTheDocument();
  });
});
