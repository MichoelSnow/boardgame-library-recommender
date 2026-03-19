import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AdminLibraryImportsPage from './AdminLibraryImportsPage';
import {
  activateLibraryImport,
  deleteLibraryImport,
  fetchLibraryImports,
  validateLibraryImportCsv,
  uploadLibraryImportCsv,
} from '../api/libraryImports';

jest.mock('../api/libraryImports', () => ({
  fetchLibraryImports: jest.fn(),
  validateLibraryImportCsv: jest.fn(),
  uploadLibraryImportCsv: jest.fn(),
  activateLibraryImport: jest.fn(),
  deleteLibraryImport: jest.fn(),
}));

describe('AdminLibraryImportsPage', () => {
  beforeEach(() => {
    fetchLibraryImports.mockReset();
    validateLibraryImportCsv.mockReset();
    uploadLibraryImportCsv.mockReset();
    activateLibraryImport.mockReset();
    deleteLibraryImport.mockReset();
  });

  test('renders import rows and allows activation', async () => {
    fetchLibraryImports.mockResolvedValue([
      {
        id: 1,
        label: 'seed',
        import_method: 'seed_existing',
        total_items: 10,
        is_active: true,
        imported_by_username: 'admin',
        created_at: '2026-03-16T10:00:00Z',
      },
      {
        id: 2,
        label: 'spring',
        import_method: 'csv_upload',
        total_items: 20,
        is_active: false,
        imported_by_username: 'admin',
        created_at: '2026-03-16T11:00:00Z',
      },
    ]);
    activateLibraryImport.mockResolvedValue({
      id: 2,
      label: 'spring',
      is_active: true,
    });

    render(
      <MemoryRouter>
        <AdminLibraryImportsPage />
      </MemoryRouter>
    );

    await screen.findByText('seed');
    const activateButton = screen.getByRole('button', { name: 'Activate' });
    fireEvent.click(activateButton);
    await waitFor(() => expect(activateLibraryImport).toHaveBeenCalledWith(2));
  });

  test('deletes an inactive import after confirmation', async () => {
    fetchLibraryImports.mockResolvedValue([
      {
        id: 2,
        label: 'spring',
        import_method: 'csv_upload',
        total_items: 20,
        is_active: false,
        imported_by_username: 'admin',
        created_at: '2026-03-16T11:00:00Z',
      },
    ]);
    deleteLibraryImport.mockResolvedValue(undefined);
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);

    render(
      <MemoryRouter>
        <AdminLibraryImportsPage />
      </MemoryRouter>
    );

    await screen.findByText('spring');
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(deleteLibraryImport).toHaveBeenCalledWith(2));
    confirmSpy.mockRestore();
  });

  test('submits csv upload form', async () => {
    fetchLibraryImports.mockResolvedValue([]);
    validateLibraryImportCsv.mockResolvedValue({
      total_rows: 2,
      valid_rows: 2,
      duplicate_rows: 0,
      invalid_rows: 0,
      unknown_id_rows: 0,
      unique_candidate_ids: 2,
      warnings_invalid_rows: [],
      warnings_unknown_ids: [],
    });
    uploadLibraryImportCsv.mockResolvedValue({
      import_record: {
        id: 3,
        label: 'spring-csv',
        total_items: 2,
      },
      skipped_duplicates: 0,
      skipped_invalid_rows: 0,
      skipped_unknown_ids: 0,
      kept_unknown_ids: 0,
    });

    render(
      <MemoryRouter>
        <AdminLibraryImportsPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(fetchLibraryImports).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText('Import label'), {
      target: { value: 'spring-csv' },
    });
    const input = screen.getByTestId('library-import-file-input');
    const file = new File(['bgg_id\n13\n42\n'], 'ids.csv', { type: 'text/csv' });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: 'Validate CSV' }));
    await waitFor(() =>
      expect(validateLibraryImportCsv).toHaveBeenCalledWith({
        file,
      })
    );
    fireEvent.click(screen.getByRole('button', { name: 'Upload CSV' }));

    await waitFor(() =>
      expect(uploadLibraryImportCsv).toHaveBeenCalledWith({
        label: 'spring-csv',
        file,
        activate: true,
        ignoreInvalidRows: true,
        allowUnknownIds: false,
      })
    );
  });
});
