import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AdminUsersPage from './AdminUsersPage';
import {
  createAdminUser,
  fetchAdminUsers,
  resetAdminUserPassword,
  updateAdminUser,
} from '../api/user';

jest.mock('../api/user', () => ({
  createAdminUser: jest.fn(),
  fetchAdminUsers: jest.fn(),
  resetAdminUserPassword: jest.fn(),
  updateAdminUser: jest.fn(),
}));

describe('AdminUsersPage', () => {
  beforeEach(() => {
    fetchAdminUsers.mockReset();
    createAdminUser.mockReset();
    updateAdminUser.mockReset();
    resetAdminUserPassword.mockReset();
    fetchAdminUsers.mockResolvedValue([
      { id: 1, username: 'admin', is_admin: true, is_active: true },
      { id: 2, username: 'staff', is_admin: false, is_active: true },
    ]);
    createAdminUser.mockResolvedValue({
      id: 3,
      username: 'librarian',
      is_admin: false,
      is_active: true,
    });
    updateAdminUser.mockResolvedValue({
      id: 2,
      username: 'staff',
      is_admin: false,
      is_active: true,
    });
    resetAdminUserPassword.mockResolvedValue({ message: 'Password reset successfully' });
  });

  test('renders paginated user table and supports search', async () => {
    render(
      <MemoryRouter>
        <AdminUsersPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(fetchAdminUsers).toHaveBeenCalled());
    expect(await screen.findByText('admin')).toBeInTheDocument();
    expect(await screen.findByText('staff')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Search username'), {
      target: { value: 'adm' },
    });
    await screen.findByText('admin');
    await waitFor(() => expect(screen.queryByText('staff')).not.toBeInTheDocument());
  });

  test('creates a user from dialog', async () => {
    render(
      <MemoryRouter>
        <AdminUsersPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(fetchAdminUsers).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Create User' }));
    fireEvent.change(screen.getByLabelText('Username'), {
      target: { value: 'librarian' },
    });
    fireEvent.change(screen.getByLabelText('Temporary Password'), {
      target: { value: 'pass1234' },
    });
    fireEvent.change(screen.getByLabelText('Confirm Password'), {
      target: { value: 'pass1234' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() =>
      expect(createAdminUser).toHaveBeenCalledWith({
        username: 'librarian',
        password: 'pass1234',
        is_admin: false,
      })
    );
  });

  test('requires matching passwords for create dialog', async () => {
    render(
      <MemoryRouter>
        <AdminUsersPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(fetchAdminUsers).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Create User' }));
    fireEvent.change(screen.getByLabelText('Username'), {
      target: { value: 'mismatch-user' },
    });
    fireEvent.change(screen.getByLabelText('Temporary Password'), {
      target: { value: 'pass1234' },
    });
    fireEvent.change(screen.getByLabelText('Confirm Password'), {
      target: { value: 'different-pass' },
    });

    expect(screen.getByRole('button', { name: 'Create' })).toBeDisabled();
    expect(screen.getByText('Passwords do not match')).toBeInTheDocument();
  });

  test('requires matching passwords for reset dialog', async () => {
    render(
      <MemoryRouter>
        <AdminUsersPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(fetchAdminUsers).toHaveBeenCalled());

    fireEvent.click(screen.getAllByRole('button', { name: 'Reset Password' })[0]);

    fireEvent.change(screen.getByLabelText('New Password'), {
      target: { value: 'reset1234' },
    });
    fireEvent.change(screen.getByLabelText('Confirm New Password'), {
      target: { value: 'mismatch1234' },
    });

    expect(screen.getByRole('button', { name: 'Reset' })).toBeDisabled();
    expect(screen.getByText('Passwords do not match')).toBeInTheDocument();
  });
});
