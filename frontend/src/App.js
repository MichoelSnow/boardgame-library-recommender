import React, { useMemo } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import GameList from './components/GameList';
import Navbar from './components/Navbar';
import './App.css';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import LoginPage from './pages/LoginPage';
import KioskSetupPage from './pages/KioskSetupPage';
import AdminPanelPage from './pages/AdminPanelPage';
import AdminThemePage from './pages/AdminThemePage';
import AdminUsersPage from './pages/AdminUsersPage';
import AdminLibraryImportsPage from './pages/AdminLibraryImportsPage';
import { useLocation } from 'react-router-dom';
import {
  ThemeSettingsProvider,
  useThemeSettings,
} from './context/ThemeSettingsContext';

// Create a client with optimized caching
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: 24 * 60 * 60 * 1000, // 24 hours
      staleTime: 30 * 60 * 1000, // 30 minutes
      refetchOnWindowFocus: false,
      retry: 1,
      networkMode: 'offlineFirst',
    },
  },
});

const AppContent = () => {
  const location = useLocation();
  const showNavbar = location.pathname !== '/login';

  return (
    <div className="app-shell">
      {showNavbar && <Navbar />}
      <main className="app-main">
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <GameList />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <AdminPanelPage />
              </AdminRoute>
            }
          />
          <Route
            path="/admin/theme"
            element={
              <AdminRoute>
                <AdminThemePage />
              </AdminRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <AdminRoute>
                <AdminUsersPage />
              </AdminRoute>
            }
          />
          <Route
            path="/admin/library-imports"
            element={
              <AdminRoute>
                <AdminLibraryImportsPage />
              </AdminRoute>
            }
          />
          <Route
            path="/kiosk/setup"
            element={
              <AdminRoute>
                <KioskSetupPage />
              </AdminRoute>
            }
          />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </main>
    </div>
  );
};

function ThemedApp() {
  const { effectivePrimaryColor } = useThemeSettings();
  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode: 'light',
          primary: {
            main: effectivePrimaryColor,
          },
          secondary: {
            main: '#dc004e',
          },
          background: {
            default: '#f5f5f5',
            paper: '#ffffff',
          },
        },
      }),
    [effectivePrimaryColor]
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <AppContent />
      </Router>
    </ThemeProvider>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeSettingsProvider>
          <ThemedApp />
        </ThemeSettingsProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
