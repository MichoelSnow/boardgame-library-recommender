import { apiClient } from './client';

export const fetchConventionKioskStatus = async () => {
  const response = await apiClient.get('/convention/kiosk/status');
  return response.data;
};
