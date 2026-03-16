import { apiClient } from './client';

export const fetchLibraryImports = async () => {
  const response = await apiClient.get('/admin/library-imports');
  return response.data;
};

export const validateLibraryImportCsv = async ({ file }) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await apiClient.post('/admin/library-imports/csv/validate', formData);
  return response.data;
};

export const uploadLibraryImportCsv = async ({
  label,
  file,
  activate = true,
  ignoreInvalidRows = true,
  allowUnknownIds = false,
}) => {
  const formData = new FormData();
  formData.append('label', label);
  formData.append('activate', String(Boolean(activate)));
  formData.append('ignore_invalid_rows', String(Boolean(ignoreInvalidRows)));
  formData.append('allow_unknown_ids', String(Boolean(allowUnknownIds)));
  formData.append('file', file);
  const response = await apiClient.post('/admin/library-imports/csv', formData);
  return response.data;
};

export const activateLibraryImport = async (importId) => {
  const response = await apiClient.post(`/admin/library-imports/${importId}/activate`);
  return response.data;
};
