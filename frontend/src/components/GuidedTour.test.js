import React from 'react';
import { render, screen } from '@testing-library/react';
import GuidedTour from './GuidedTour';

describe('GuidedTour library name copy', () => {
  test('includes configured library name in welcome step title', () => {
    render(
      <GuidedTour
        isOpen={true}
        onClose={jest.fn()}
        libraryName="PAX East"
      />
    );

    expect(
      screen.getByText('Welcome to the PAX East Board Game Catalog!')
    ).toBeInTheDocument();
  });

  test('falls back to default welcome title when no library name is set', () => {
    render(<GuidedTour isOpen={true} onClose={jest.fn()} libraryName="" />);

    expect(
      screen.getByText('Welcome to the Board Game Catalog!')
    ).toBeInTheDocument();
  });
});
