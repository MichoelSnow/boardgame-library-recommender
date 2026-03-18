import React from 'react';
import { render, screen } from '@testing-library/react';
import HelpDialog from './HelpDialog';

describe('HelpDialog library name copy', () => {
  test('includes configured library name prefix when provided', () => {
    render(
      <HelpDialog
        open={true}
        onClose={jest.fn()}
        onStartTour={jest.fn()}
        libraryName="PAX East"
      />
    );

    expect(
      screen.getByText('PAX East Board Game Catalog Help Guide')
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Welcome to the PAX East Board Game Library!/i)
    ).toBeInTheDocument();
  });

  test('falls back to default copy when library name is empty', () => {
    render(
      <HelpDialog
        open={true}
        onClose={jest.fn()}
        onStartTour={jest.fn()}
        libraryName=""
      />
    );

    expect(screen.getByText('Board Game Catalog Help Guide')).toBeInTheDocument();
    expect(
      screen.getByText(/Welcome to the Board Game Library!/i)
    ).toBeInTheDocument();
  });
});
