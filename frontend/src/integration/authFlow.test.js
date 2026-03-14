import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { AuthProvider } from '../context/AuthContext';
import LoginPage from '../pages/LoginPage';
import { getMswState } from '../test/msw/state';

describe('auth flow integration', () => {
  test('logs in and redirects to home route', async () => {
    render(
      <MemoryRouter
        initialEntries={['/login']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<div>Home</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText(/username/i), 'demo');
    await userEvent.type(screen.getByLabelText(/password/i), 'pass123');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await screen.findByText('Home');
    await waitFor(() => {
      expect(localStorage.getItem('token')).toBe('token-abc');
    });
    expect(getMswState().tokenRequests).toBe(1);
  });

  test('shows login error for invalid credentials', async () => {
    const consoleErrorSpy = jest
      .spyOn(console, 'error')
      .mockImplementation(() => {});
    try {
      render(
        <MemoryRouter
          initialEntries={['/login']}
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <AuthProvider>
            <LoginPage />
          </AuthProvider>
        </MemoryRouter>
      );

      await userEvent.type(screen.getByLabelText(/username/i), 'demo');
      await userEvent.type(screen.getByLabelText(/password/i), 'wrong');
      await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

      expect(await screen.findByText(/failed to log in/i)).toBeInTheDocument();
    } finally {
      consoleErrorSpy.mockRestore();
    }
  });
});
