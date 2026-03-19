import React, { useContext, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Box,
  Button,
  Tooltip,
} from '@mui/material';
import HomeIcon from '@mui/icons-material/Home';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import FeedbackIcon from '@mui/icons-material/Feedback';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import AuthContext from '../context/AuthContext';
import HelpDialog from './HelpDialog';
import GuidedTour from './GuidedTour';
import SuggestionsModal from './SuggestionsModal';
import PasswordChangeModal from './PasswordChangeModal';
import { useThemeSettings } from '../context/ThemeSettingsContext';

function Navbar() {
  const navigate = useNavigate();
  const { user, logout } = useContext(AuthContext);
  const { navbarTextColor, primaryColor, libraryName = '' } = useThemeSettings();
  const libraryNamePrefix = libraryName ? `${libraryName} ` : '';
  const isGuestUser = Boolean(user?.is_guest);
  const [helpOpen, setHelpOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [passwordChangeOpen, setPasswordChangeOpen] = useState(false);

  return (
    <AppBar
      position="static"
      sx={{
        backgroundColor: primaryColor,
        color: navbarTextColor,
      }}
    >
      <Toolbar>
        <IconButton
          edge="start"
          color="inherit"
          aria-label="home"
          onClick={() => navigate('/')}
        >
          <HomeIcon />
        </IconButton>
        <Typography
          variant="h6"
          noWrap
          component="div"
          sx={{ flexGrow: 1, display: { xs: 'none', sm: 'block' } }}
        >
          {libraryNamePrefix}Board Game Library & Recommendation Engine
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Tooltip title="Help & User Guide">
            <Button
              color="inherit"
              onClick={() => setHelpOpen(true)}
              startIcon={<HelpOutlineIcon />}
              sx={{ mr: 2, textTransform: 'none' }}
              data-tour="help-button"
            >
              <Typography sx={{ display: { xs: 'none', md: 'block' } }}>
                How to Use This Site
              </Typography>
            </Button>
          </Tooltip>

          {user && (
            <Tooltip title="Submit feedback or suggestions">
              <Button
                color="inherit"
                onClick={() => setSuggestionsOpen(true)}
                startIcon={<FeedbackIcon />}
                sx={{ mr: 2, textTransform: 'none' }}
              >
                <Typography sx={{ display: { xs: 'none', md: 'block' } }}>
                  Suggestions
                </Typography>
              </Button>
            </Tooltip>
          )}

          {user?.is_admin && !isGuestUser && (
            <Tooltip title="Admin tools">
              <Button
                color="inherit"
                onClick={() => navigate('/admin')}
                startIcon={<AdminPanelSettingsIcon />}
                sx={{ mr: 2, textTransform: 'none' }}
              >
                <Typography sx={{ display: { xs: 'none', md: 'block' } }}>
                  Admin Panel
                </Typography>
              </Button>
            </Tooltip>
          )}

          {user && !isGuestUser && (
            <Tooltip title="Change your password">
              <Button
                color="inherit"
                onClick={() => setPasswordChangeOpen(true)}
                startIcon={<VpnKeyIcon />}
                sx={{ mr: 2, textTransform: 'none' }}
              >
                <Typography sx={{ display: { xs: 'none', md: 'block' } }}>
                  Change Password
                </Typography>
              </Button>
            </Tooltip>
          )}
          
          {user && (
            <Button color="inherit" onClick={logout}>
              {isGuestUser ? 'Reset Session' : 'Logout'}
            </Button>
          )}
        </Box>
      </Toolbar>
      <HelpDialog 
        open={helpOpen} 
        onClose={() => setHelpOpen(false)}
        onStartTour={() => setTourOpen(true)}
        libraryName={libraryName}
      />
      <GuidedTour 
        isOpen={tourOpen} 
        onClose={() => setTourOpen(false)}
        libraryName={libraryName}
      />
      <SuggestionsModal 
        open={suggestionsOpen} 
        onClose={() => setSuggestionsOpen(false)}
      />
      <PasswordChangeModal 
        open={passwordChangeOpen} 
        onClose={() => setPasswordChangeOpen(false)}
      />
    </AppBar>
  );
}

export default Navbar; 
