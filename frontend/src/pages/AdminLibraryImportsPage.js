import React from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import {
  activateLibraryImport,
  deleteLibraryImport,
  fetchLibraryImports,
  refreshCatalog,
  validateLibraryImportCsv,
  uploadLibraryImportCsv,
} from '../api/libraryImports';

const formatTimestamp = (value) => {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '—';
  }
  return parsed.toLocaleString();
};

const AdminLibraryImportsPage = () => {
  const [imports, setImports] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [success, setSuccess] = React.useState('');
  const [label, setLabel] = React.useState('');
  const [file, setFile] = React.useState(null);
  const [activateOnUpload, setActivateOnUpload] = React.useState(true);
  const [ignoreInvalidRows, setIgnoreInvalidRows] = React.useState(true);
  const [allowUnknownIds, setAllowUnknownIds] = React.useState(false);
  const [validationResult, setValidationResult] = React.useState(null);
  const [validating, setValidating] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [activatingId, setActivatingId] = React.useState(null);
  const [deletingId, setDeletingId] = React.useState(null);
  const [refreshingCatalog, setRefreshingCatalog] = React.useState(false);

  const loadImports = React.useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await fetchLibraryImports();
      setImports(payload);
    } catch (_error) {
      setError('Failed to load import history.');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadImports();
  }, [loadImports]);

  const onValidate = async () => {
    setError('');
    setSuccess('');
    setValidationResult(null);
    if (!file) {
      setError('Please choose a CSV file.');
      return;
    }
    setValidating(true);
    try {
      const payload = await validateLibraryImportCsv({ file });
      setValidationResult(payload);
      setSuccess('Validation complete. Review warnings before import.');
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || 'Validation failed.');
    } finally {
      setValidating(false);
    }
  };

  const onSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    if (!label.trim()) {
      setError('Label is required.');
      return;
    }
    if (!file) {
      setError('Please choose a CSV file.');
      return;
    }
    if (!validationResult) {
      setError('Please validate the CSV before uploading.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = await uploadLibraryImportCsv({
        label: label.trim(),
        file,
        activate: activateOnUpload,
        ignoreInvalidRows,
        allowUnknownIds,
      });
      setSuccess(
        `Uploaded "${payload.import_record.label}" (${payload.import_record.total_items} IDs). ` +
          `Skipped invalid: ${payload.skipped_invalid_rows}, skipped unknown: ${payload.skipped_unknown_ids}, kept unknown: ${payload.kept_unknown_ids}.`
      );
      setLabel('');
      setFile(null);
      setValidationResult(null);
      await loadImports();
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || 'Upload failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const onActivate = async (importId) => {
    setActivatingId(importId);
    setError('');
    setSuccess('');
    try {
      const payload = await activateLibraryImport(importId);
      setSuccess(`Activated import "${payload.label}".`);
      await loadImports();
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || 'Activation failed.');
    } finally {
      setActivatingId(null);
    }
  };

  const onDelete = async (item) => {
    const confirmed = window.confirm(
      `Delete import "${item.label}"? This cannot be undone.`
    );
    if (!confirmed) {
      return;
    }

    setDeletingId(item.id);
    setError('');
    setSuccess('');
    try {
      await deleteLibraryImport(item.id);
      setSuccess(`Deleted import "${item.label}".`);
      await loadImports();
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || 'Delete failed.');
    } finally {
      setDeletingId(null);
    }
  };

  const onRefreshCatalog = async () => {
    setRefreshingCatalog(true);
    setError('');
    setSuccess('');
    try {
      const payload = await refreshCatalog();
      setSuccess(payload?.message || 'Catalog refresh requested.');
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || 'Catalog refresh request failed.');
    } finally {
      setRefreshingCatalog(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 1265, mx: 'auto', mt: 4, px: 2.5 }}>
      <Card>
        <CardContent>
          <Stack spacing={2.5}>
            <Typography variant="h4" component="h1">
              Library Imports
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Upload validated Library BGG ID CSV files, label each import, and switch the active library version.
            </Typography>
            <Box>
              <Button
                variant="outlined"
                onClick={onRefreshCatalog}
                disabled={refreshingCatalog}
              >
                {refreshingCatalog ? 'Requesting...' : 'Refresh Catalog'}
              </Button>
            </Box>

            {error && <Alert severity="error">{error}</Alert>}
            {success && <Alert severity="success">{success}</Alert>}

            <Box component="form" onSubmit={onSubmit}>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ md: 'center' }}>
                <TextField
                  label="Import label"
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                  size="small"
                  sx={{ minWidth: 260 }}
                />
                <Button variant="outlined" component="label">
                  {file ? file.name : 'Choose CSV'}
                  <input
                    hidden
                    data-testid="library-import-file-input"
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(event) => {
                      const selected = event.target.files && event.target.files[0];
                      setFile(selected || null);
                      setValidationResult(null);
                    }}
                  />
                </Button>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={activateOnUpload}
                      onChange={(event) => setActivateOnUpload(event.target.checked)}
                    />
                  }
                  label="Activate after upload"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={ignoreInvalidRows}
                      onChange={(event) => setIgnoreInvalidRows(event.target.checked)}
                    />
                  }
                  label="Skip invalid rows"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={allowUnknownIds}
                      onChange={(event) => setAllowUnknownIds(event.target.checked)}
                    />
                  }
                  label="Keep unknown IDs"
                />
                <Button variant="outlined" onClick={onValidate} disabled={validating}>
                  {validating ? 'Validating...' : 'Validate CSV'}
                </Button>
                <Button type="submit" variant="contained" disabled={submitting || !validationResult}>
                  {submitting ? 'Uploading...' : 'Upload CSV'}
                </Button>
              </Stack>
            </Box>

            {validationResult && (
              <Stack spacing={1}>
                <Typography variant="h6">Validation Summary</Typography>
                <Typography variant="body2" color="text.secondary">
                  Rows: {validationResult.total_rows}, valid candidates: {validationResult.valid_rows}, duplicates: {validationResult.duplicate_rows}, invalid: {validationResult.invalid_rows}, unknown IDs: {validationResult.unknown_id_rows}
                </Typography>
                {validationResult.warnings_invalid_rows.length > 0 && (
                  <Alert severity="warning">
                    Invalid rows (first {validationResult.warnings_invalid_rows.length} shown):{' '}
                    {validationResult.warnings_invalid_rows
                      .slice(0, 10)
                      .map((item) => `row ${item.row_number}: ${item.value}`)
                      .join('; ')}
                  </Alert>
                )}
                {validationResult.warnings_unknown_ids.length > 0 && (
                  <Alert severity="warning">
                    Unknown IDs (first {validationResult.warnings_unknown_ids.length} shown):{' '}
                    {validationResult.warnings_unknown_ids
                      .slice(0, 10)
                      .map((item) => `row ${item.row_number}: ${item.value}`)
                      .join('; ')}
                  </Alert>
                )}
              </Stack>
            )}

            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Label</TableCell>
                  <TableCell>Method</TableCell>
                  <TableCell>Items</TableCell>
                  <TableCell>Imported By</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {imports.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.label}</TableCell>
                    <TableCell>{item.import_method}</TableCell>
                    <TableCell>{item.total_items}</TableCell>
                    <TableCell>{item.imported_by_username || '—'}</TableCell>
                    <TableCell>{formatTimestamp(item.created_at)}</TableCell>
                    <TableCell>{item.is_active ? 'Active' : 'Inactive'}</TableCell>
                    <TableCell align="right">
                      {item.is_active ? (
                        <Typography variant="body2" color="text.secondary">
                          Current
                        </Typography>
                      ) : (
                        <Stack direction="row" spacing={1} justifyContent="flex-end">
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => onActivate(item.id)}
                            disabled={activatingId === item.id || deletingId === item.id}
                          >
                            {activatingId === item.id ? 'Activating...' : 'Activate'}
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            color="error"
                            onClick={() => onDelete(item)}
                            disabled={deletingId === item.id || activatingId === item.id}
                          >
                            {deletingId === item.id ? 'Deleting...' : 'Delete'}
                          </Button>
                        </Stack>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {!loading && imports.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7}>
                      <Typography variant="body2" color="text.secondary">
                        No imports found.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
};

export default AdminLibraryImportsPage;
