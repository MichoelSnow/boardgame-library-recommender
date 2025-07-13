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
import AuthContext from '../context/AuthContext';
import HelpDialog from './HelpDialog';
import GuidedTour from './GuidedTour';

function Navbar() {
  const navigate = useNavigate();
  const { user, logout } = useContext(AuthContext);
  const [helpOpen, setHelpOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);

  return (
    <AppBar position="static">
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
          PAX TableTop Board Game Catalog
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Tooltip title="Help & User Guide">
            <Button
              color="inherit"
              onClick={() => setHelpOpen(true)}
              startIcon={<HelpOutlineIcon />}
              sx={{ mr: 3, textTransform: 'none' }}
              data-tour="help-button"
            >
              <Typography sx={{ display: { xs: 'none', md: 'block' } }}>
                How to Use This Site
              </Typography>
            </Button>
          </Tooltip>
          
          {user && (
            <Button color="inherit" onClick={logout}>Logout</Button>
          )}
        </Box>
      </Toolbar>
      <HelpDialog 
        open={helpOpen} 
        onClose={() => setHelpOpen(false)}
        onStartTour={() => setTourOpen(true)}
      />
      <GuidedTour 
        isOpen={tourOpen} 
        onClose={() => setTourOpen(false)} 
      />
    </AppBar>
  );
}

export default Navbar; 