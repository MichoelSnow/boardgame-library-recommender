import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AdminPanelPage from './AdminPanelPage';

describe('AdminPanelPage', () => {
  test('renders links to kiosk, theme, user management, and library imports pages', () => {
    render(
      <MemoryRouter>
        <AdminPanelPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: 'Kiosk Mode' })).toHaveAttribute(
      'href',
      '/kiosk/setup'
    );
    expect(screen.getByRole('link', { name: 'Theme Color' })).toHaveAttribute(
      'href',
      '/admin/theme'
    );
    expect(screen.getByRole('link', { name: 'User Management' })).toHaveAttribute(
      'href',
      '/admin/users'
    );
    expect(screen.getByRole('link', { name: 'Library Imports' })).toHaveAttribute(
      'href',
      '/admin/library-imports'
    );
  });
});
