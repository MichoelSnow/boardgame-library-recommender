import { apiClient } from './client';

export const fetchConventionKioskStatus = async () => {
  const response = await apiClient.get('/convention/kiosk/status');
  return response.data;
};

export const enrollConventionKioskAdmin = async () => {
  const response = await apiClient.post('/convention/kiosk/admin/enroll');
  return response.data;
};

export const unenrollConventionKioskAdmin = async () => {
  const response = await apiClient.post('/convention/kiosk/admin/unenroll');
  return response.data;
};
