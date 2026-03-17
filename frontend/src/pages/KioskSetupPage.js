import React, { useMemo, useState } from 'react';
import { useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Stack,
  Typography,
} from '@mui/material';
import AuthContext from '../context/AuthContext';
import {
  enrollConventionKioskAdmin,
  fetchConventionKioskStatus,
  unenrollConventionKioskAdmin,
} from '../api/convention';

const KioskSetupPage = () => {
  const { logout } = useContext(AuthContext);
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [pendingAction, setPendingAction] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const refreshStatus = async () => {
    setLoadingStatus(true);
    setErrorMessage('');
    try {
      const payload = await fetchConventionKioskStatus();
      setStatus(payload);
    } catch (error) {
      setErrorMessage(error?.response?.data?.detail || 'Failed to load kiosk status.');
    } finally {
      setLoadingStatus(false);
    }
  };

  React.useEffect(() => {
    refreshStatus();
  }, []);

  const conventionModeEnabled = useMemo(
    () => Boolean(status?.convention_mode),
    [status],
  );
  const kioskModeEnabled = useMemo(() => Boolean(status?.kiosk_mode), [status]);

  const handleEnroll = async () => {
    setPendingAction(true);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      await enrollConventionKioskAdmin();
      setSuccessMessage('This browser is now enrolled for kiosk mode. Switching to guest session...');
      await logout();
      navigate('/');
    } catch (error) {
      setErrorMessage(error?.response?.data?.detail || 'Failed to enroll kiosk mode.');
    } finally {
      setPendingAction(false);
    }
  };

  const handleUnenroll = async () => {
    setPendingAction(true);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      await unenrollConventionKioskAdmin();
      setSuccessMessage('Kiosk mode has been removed for this browser.');
      await refreshStatus();
    } catch (error) {
      setErrorMessage(error?.response?.data?.detail || 'Failed to unenroll kiosk mode.');
    } finally {
      setPendingAction(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 720, mx: 'auto', mt: 4, px: 2 }}>
      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h4" component="h1">
              Kiosk Setup
            </Typography>
            <Typography variant="body1">
              Admin-only tool to enroll or remove kiosk mode for this browser profile.
            </Typography>

            {loadingStatus ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={20} />
                <Typography variant="body2">Loading status...</Typography>
              </Box>
            ) : (
              <Stack spacing={1}>
                <Typography variant="body2">
                  Convention mode: <strong>{conventionModeEnabled ? 'ON' : 'OFF'}</strong>
                </Typography>
                <Typography variant="body2">
                  Kiosk mode on this browser: <strong>{kioskModeEnabled ? 'ON' : 'OFF'}</strong>
                </Typography>
              </Stack>
            )}

            {!conventionModeEnabled && (
              <Alert severity="warning">
                Convention mode is currently disabled. Enable convention profile before enrollment.
              </Alert>
            )}

            {errorMessage && <Alert severity="error">{errorMessage}</Alert>}
            {successMessage && <Alert severity="success">{successMessage}</Alert>}

            <Stack direction="row" spacing={2}>
              <Button
                variant="contained"
                onClick={handleEnroll}
                disabled={pendingAction || loadingStatus || !conventionModeEnabled}
              >
                Enroll This Device
              </Button>
              <Button
                variant="outlined"
                color="warning"
                onClick={handleUnenroll}
                disabled={pendingAction || loadingStatus}
              >
                Remove Kiosk Mode
              </Button>
              <Button
                variant="text"
                onClick={refreshStatus}
                disabled={pendingAction || loadingStatus}
              >
                Refresh Status
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
};

export default KioskSetupPage;
