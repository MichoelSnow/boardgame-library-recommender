import React, { useContext } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Box, Button, CircularProgress, Typography } from '@mui/material';
import AuthContext from '../context/AuthContext';

const AdminRoute = ({ children }) => {
  const { user, loading, switchToAdminLogin } = useContext(AuthContext);
  const location = useLocation();
  const navigate = useNavigate();

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!user.is_admin) {
    const isGuest = Boolean(user.is_guest);
    return (
      <Box sx={{ maxWidth: 640, mx: 'auto', mt: 8, px: 2 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Admin Access Required
        </Typography>
        <Typography variant="body1">
          You must be an admin user to manage kiosk enrollment.
        </Typography>
        {isGuest && (
          <Button
            sx={{ mt: 3 }}
            variant="contained"
            onClick={() => {
              switchToAdminLogin();
              navigate('/login?admin=1', { state: { from: location } });
            }}
          >
            Switch to Admin Login
          </Button>
        )}
      </Box>
    );
  }

  return children;
};

export default AdminRoute;
