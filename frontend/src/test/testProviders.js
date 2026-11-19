import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
      mutations: {
        retry: false,
        gcTime: Infinity,
      },
    },
  });

export const withQueryClient = (ui, queryClient = createTestQueryClient()) => (
  <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
);
