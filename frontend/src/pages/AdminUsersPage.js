import React from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import {
  createAdminUser,
  fetchAdminUsers,
  resetAdminUserPassword,
  updateAdminUser,
} from '../api/user';

const DEFAULT_ROWS_PER_PAGE = 10;

const filterUsers = (users, search, roleFilter, statusFilter) => {
  const q = search.trim().toLowerCase();
  return users.filter((user) => {
    const matchesSearch = !q || user.username.toLowerCase().includes(q);
    const matchesRole =
      roleFilter === 'all' ||
      (roleFilter === 'admin' && user.is_admin) ||
      (roleFilter === 'staff' && !user.is_admin);
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'active' && user.is_active) ||
      (statusFilter === 'inactive' && !user.is_active);
    return matchesSearch && matchesRole && matchesStatus;
  });
};

const AdminUsersPage = () => {
  const [users, setUsers] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [success, setSuccess] = React.useState('');
  const [search, setSearch] = React.useState('');
  const [roleFilter, setRoleFilter] = React.useState('all');
  const [statusFilter, setStatusFilter] = React.useState('all');
  const [page, setPage] = React.useState(0);
  const [rowsPerPage, setRowsPerPage] = React.useState(DEFAULT_ROWS_PER_PAGE);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [editOpen, setEditOpen] = React.useState(false);
  const [resetOpen, setResetOpen] = React.useState(false);
  const [selectedUser, setSelectedUser] = React.useState(null);
  const [createForm, setCreateForm] = React.useState({
    username: '',
    password: '',
    confirm_password: '',
    is_admin: false,
  });
  const [editForm, setEditForm] = React.useState({
    is_admin: false,
    is_active: true,
  });
  const [resetPassword, setResetPassword] = React.useState('');
  const [resetPasswordConfirm, setResetPasswordConfirm] = React.useState('');
  const [showCreatePassword, setShowCreatePassword] = React.useState(false);
  const [showCreateConfirmPassword, setShowCreateConfirmPassword] =
    React.useState(false);
  const [showResetPassword, setShowResetPassword] = React.useState(false);
  const [showResetConfirmPassword, setShowResetConfirmPassword] =
    React.useState(false);

  const loadUsers = React.useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await fetchAdminUsers();
      setUsers(payload);
    } catch (_error) {
      setError('Failed to load users.');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const visibleUsers = React.useMemo(
    () => filterUsers(users, search, roleFilter, statusFilter),
    [users, search, roleFilter, statusFilter]
  );
  const pagedUsers = React.useMemo(() => {
    const start = page * rowsPerPage;
    return visibleUsers.slice(start, start + rowsPerPage);
  }, [page, rowsPerPage, visibleUsers]);

  return (
    <Box sx={{ maxWidth: 1100, mx: 'auto', mt: 4, px: 2 }}>
      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h4" component="h1">
              User Management
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Search, filter, and manage users at scale.
            </Typography>
            {error && <Alert severity="error">{error}</Alert>}
            {success && <Alert severity="success">{success}</Alert>}

            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
              <TextField
                label="Search username"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(0);
                }}
                size="small"
                sx={{ minWidth: 260 }}
              />
              <FormControl size="small" sx={{ minWidth: 160 }}>
                <InputLabel id="role-filter-label">Role</InputLabel>
                <Select
                  labelId="role-filter-label"
                  value={roleFilter}
                  label="Role"
                  onChange={(event) => {
                    setRoleFilter(event.target.value);
                    setPage(0);
                  }}
                >
                  <MenuItem value="all">All roles</MenuItem>
                  <MenuItem value="admin">Admin</MenuItem>
                  <MenuItem value="staff">Staff</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 160 }}>
                <InputLabel id="status-filter-label">Status</InputLabel>
                <Select
                  labelId="status-filter-label"
                  value={statusFilter}
                  label="Status"
                  onChange={(event) => {
                    setStatusFilter(event.target.value);
                    setPage(0);
                  }}
                >
                  <MenuItem value="all">All statuses</MenuItem>
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="inactive">Inactive</MenuItem>
                </Select>
              </FormControl>
              <Box sx={{ flexGrow: 1 }} />
              <Button variant="contained" onClick={() => setCreateOpen(true)}>
                Create User
              </Button>
            </Stack>

            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Username</TableCell>
                    <TableCell>Role</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {pagedUsers.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>{user.username}</TableCell>
                      <TableCell>{user.is_admin ? 'Admin' : 'Staff'}</TableCell>
                      <TableCell>{user.is_active ? 'Active' : 'Inactive'}</TableCell>
                      <TableCell align="right">
                        <Stack direction="row" justifyContent="flex-end" spacing={1}>
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => {
                              setSelectedUser(user);
                              setEditForm({
                                is_admin: user.is_admin,
                                is_active: user.is_active,
                              });
                              setEditOpen(true);
                            }}
                          >
                            Edit
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => {
                              setSelectedUser(user);
                              setResetPassword('');
                              setResetPasswordConfirm('');
                              setResetOpen(true);
                            }}
                          >
                            Reset Password
                          </Button>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!loading && pagedUsers.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4}>
                        <Typography variant="body2" color="text.secondary">
                          No users match the current filters.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>

            <TablePagination
              component="div"
              count={visibleUsers.length}
              page={page}
              onPageChange={(_event, nextPage) => setPage(nextPage)}
              rowsPerPage={rowsPerPage}
              onRowsPerPageChange={(event) => {
                setRowsPerPage(Number(event.target.value));
                setPage(0);
              }}
              rowsPerPageOptions={[10, 25, 50]}
            />
          </Stack>
        </CardContent>
      </Card>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create User</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Username"
              value={createForm.username}
              onChange={(event) =>
                setCreateForm((prev) => ({ ...prev, username: event.target.value }))
              }
            />
            <TextField
              label="Temporary Password"
              type={showCreatePassword ? 'text' : 'password'}
              value={createForm.password}
              onChange={(event) =>
                setCreateForm((prev) => ({ ...prev, password: event.target.value }))
              }
              helperText="Minimum 6 characters"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label="toggle create password visibility"
                      onClick={() => setShowCreatePassword((prev) => !prev)}
                      edge="end"
                    >
                      {showCreatePassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              label="Confirm Password"
              type={showCreateConfirmPassword ? 'text' : 'password'}
              value={createForm.confirm_password}
              onChange={(event) =>
                setCreateForm((prev) => ({
                  ...prev,
                  confirm_password: event.target.value,
                }))
              }
              error={
                createForm.confirm_password.length > 0 &&
                createForm.confirm_password !== createForm.password
              }
              helperText={
                createForm.confirm_password.length > 0 &&
                createForm.confirm_password !== createForm.password
                  ? 'Passwords do not match'
                  : ''
              }
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label="toggle create confirm password visibility"
                      onClick={() => setShowCreateConfirmPassword((prev) => !prev)}
                      edge="end"
                    >
                      {showCreateConfirmPassword ? (
                        <VisibilityOffIcon />
                      ) : (
                        <VisibilityIcon />
                      )}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={createForm.is_admin}
                  onChange={(event) =>
                    setCreateForm((prev) => ({ ...prev, is_admin: event.target.checked }))
                  }
                />
              }
              label="Admin user"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={async () => {
              setError('');
              setSuccess('');
              try {
                await createAdminUser({
                  username: createForm.username.trim(),
                  password: createForm.password,
                  is_admin: createForm.is_admin,
                });
                setCreateForm({
                  username: '',
                  password: '',
                  confirm_password: '',
                  is_admin: false,
                });
                setCreateOpen(false);
                setSuccess('User created successfully.');
                await loadUsers();
              } catch (requestError) {
                setError(
                  requestError?.response?.data?.detail || 'Failed to create user.'
                );
              }
            }}
            disabled={
              !createForm.username.trim() ||
              createForm.password.length < 6 ||
              createForm.confirm_password !== createForm.password
            }
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Edit User</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography variant="body2">
              Editing: <strong>{selectedUser?.username}</strong>
            </Typography>
            <FormControlLabel
              control={
                <Checkbox
                  checked={editForm.is_admin}
                  onChange={(event) =>
                    setEditForm((prev) => ({ ...prev, is_admin: event.target.checked }))
                  }
                />
              }
              label="Admin"
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={editForm.is_active}
                  onChange={(event) =>
                    setEditForm((prev) => ({ ...prev, is_active: event.target.checked }))
                  }
                />
              }
              label="Active"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={async () => {
              if (!selectedUser) {
                return;
              }
              setError('');
              setSuccess('');
              try {
                await updateAdminUser(selectedUser.id, editForm);
                setEditOpen(false);
                setSuccess(`Updated ${selectedUser.username}.`);
                await loadUsers();
              } catch (requestError) {
                setError(
                  requestError?.response?.data?.detail || 'Failed to update user.'
                );
              }
            }}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={resetOpen} onClose={() => setResetOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Reset Password</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography variant="body2">
              Reset password for: <strong>{selectedUser?.username}</strong>
            </Typography>
            <TextField
              label="New Password"
              type={showResetPassword ? 'text' : 'password'}
              value={resetPassword}
              onChange={(event) => setResetPassword(event.target.value)}
              helperText="Minimum 6 characters"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label="toggle reset password visibility"
                      onClick={() => setShowResetPassword((prev) => !prev)}
                      edge="end"
                    >
                      {showResetPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              label="Confirm New Password"
              type={showResetConfirmPassword ? 'text' : 'password'}
              value={resetPasswordConfirm}
              onChange={(event) => setResetPasswordConfirm(event.target.value)}
              error={
                resetPasswordConfirm.length > 0 &&
                resetPasswordConfirm !== resetPassword
              }
              helperText={
                resetPasswordConfirm.length > 0 &&
                resetPasswordConfirm !== resetPassword
                  ? 'Passwords do not match'
                  : ''
              }
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label="toggle reset confirm password visibility"
                      onClick={() => setShowResetConfirmPassword((prev) => !prev)}
                      edge="end"
                    >
                      {showResetConfirmPassword ? (
                        <VisibilityOffIcon />
                      ) : (
                        <VisibilityIcon />
                      )}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResetOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={async () => {
              if (!selectedUser) {
                return;
              }
              setError('');
              setSuccess('');
              try {
                await resetAdminUserPassword(selectedUser.id, resetPassword);
                setResetOpen(false);
                setSuccess(`Password reset for ${selectedUser.username}.`);
              } catch (requestError) {
                setError(
                  requestError?.response?.data?.detail ||
                    'Failed to reset user password.'
                );
              }
            }}
            disabled={
              resetPassword.length < 6 ||
              resetPasswordConfirm.length < 6 ||
              resetPasswordConfirm !== resetPassword
            }
          >
            Reset
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AdminUsersPage;
