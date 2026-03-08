import axios from 'axios';
import { apiBaseUrl } from '../config';

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
});

export const setAuthToken = (token) => {
  if (token) {
    apiClient.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common.Authorization;
  }
};

export const clearAuthToken = () => {
  delete apiClient.defaults.headers.common.Authorization;
};
