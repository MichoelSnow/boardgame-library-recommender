import React, { useState, useContext } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import {
  Container,
  Paper,
  Box,
  Typography,
  Tabs,
  Tab,
  TextField,
  Button,
  Alert,
  CircularProgress
} from '@mui/material';
import AuthContext from '../context/AuthContext';

function TabPanel(props) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const LoginPage = () => {
  const [tabIndex, setTabIndex] = useState(0);
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const { user, login } = useContext(AuthContext);
  const location = useLocation();

  const handleTabChange = (event, newValue) => {
    setError('');
    setSuccess('');
    setTabIndex(newValue);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(loginUsername, loginPassword);
    } catch (err) {
      setError('Failed to log in. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  if (user) {
    return <Navigate to={location.state?.from?.pathname || '/'} replace />;
  }

  return (
    <Container component="main" maxWidth="xs" sx={{ mt: 8 }}>
      <Paper elevation={6} sx={{ p: 2, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Typography component="h1" variant="h5">
          Board Game Recommender
        </Typography>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', width: '100%' }}>
          <Tabs value={tabIndex} onChange={handleTabChange} variant="fullWidth">
            <Tab label="Login" />
          </Tabs>
        </Box>
        <TabPanel value={tabIndex} index={0}>
          <Box component="form" onSubmit={handleLogin} noValidate sx={{ mt: 1 }}>
            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}
            <TextField
              margin="normal"
              required
              fullWidth
              label="Username"
              value={loginUsername}
              onChange={(e) => setLoginUsername(e.target.value)}
              autoFocus
            />
            <TextField
              margin="normal"
              required
              fullWidth
              label="Password"
              type="password"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
            />
            <Button
              type="submit"
              fullWidth
              variant="contained"
              sx={{ mt: 3, mb: 2 }}
              disabled={loading}
            >
              {loading ? <CircularProgress size={24} /> : 'Sign In'}
            </Button>
          </Box>
        </TabPanel>
      </Paper>
    </Container>
  );
};

export default LoginPage; 
