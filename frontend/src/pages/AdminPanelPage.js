import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Box, Button, Card, CardContent, Stack, Typography } from '@mui/material';

const AdminPanelPage = () => {
  return (
    <Box sx={{ maxWidth: 720, mx: 'auto', mt: 4, px: 2 }}>
      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h4" component="h1">
              Admin Panel
            </Typography>
            <Typography variant="body1">
              Choose an admin function.
            </Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <Button variant="contained" component={RouterLink} to="/kiosk/setup">
                Kiosk Mode
              </Button>
              <Button variant="contained" component={RouterLink} to="/admin/theme">
                Theme Color
              </Button>
              <Button variant="contained" component={RouterLink} to="/admin/users">
                User Management
              </Button>
              <Button
                variant="contained"
                component={RouterLink}
                to="/admin/library-imports"
              >
                Library Imports
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
};

export default AdminPanelPage;
