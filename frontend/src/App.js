import React from 'react';
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
import { useLocation } from 'react-router-dom';

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

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#904799',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
      paper: '#ffffff',
    },
  },
});

const AppContent = () => {
  const location = useLocation();
  const showNavbar = location.pathname !== '/login';

  return (
    <>
      {showNavbar && <Navbar />}
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
          path="/kiosk/setup"
          element={
            <AdminRoute>
              <KioskSetupPage />
            </AdminRoute>
          }
        />
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    </>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Router future={{ 
          v7_startTransition: true,
          v7_relativeSplatPath: true 
        }}>
            <AppContent />
        </Router>
      </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App; 
