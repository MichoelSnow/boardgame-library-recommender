import React, { createContext, useState, useEffect, useCallback } from 'react';
import { fetchConventionGuestToken, fetchCurrentUser, loginWithPassword } from '../api/auth';
import { fetchConventionKioskStatus } from '../api/convention';
import { clearAuthToken, setAuthToken } from '../api/client';

const AuthContext = createContext();
const USER_TOKEN_STORAGE_KEY = 'token';
const GUEST_TOKEN_STORAGE_KEY = 'guest_token';
const SUPPRESS_AUTO_GUEST_LOGIN_KEY = 'suppress_auto_guest_login';

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(
      () => localStorage.getItem(USER_TOKEN_STORAGE_KEY) || sessionStorage.getItem(GUEST_TOKEN_STORAGE_KEY)
    );
    const [loading, setLoading] = useState(true);

    const clearTokenState = useCallback(() => {
        setUser(null);
        setToken(null);
        localStorage.removeItem(USER_TOKEN_STORAGE_KEY);
        sessionStorage.removeItem(GUEST_TOKEN_STORAGE_KEY);
        clearAuthToken();
    }, []);

    const setUserToken = useCallback((nextToken) => {
      setToken(nextToken);
      localStorage.setItem(USER_TOKEN_STORAGE_KEY, nextToken);
      sessionStorage.removeItem(GUEST_TOKEN_STORAGE_KEY);
      setAuthToken(nextToken);
    }, []);

    const setGuestToken = useCallback((nextToken) => {
      setToken(nextToken);
      sessionStorage.setItem(GUEST_TOKEN_STORAGE_KEY, nextToken);
      localStorage.removeItem(USER_TOKEN_STORAGE_KEY);
      setAuthToken(nextToken);
    }, []);

    const shouldSuppressAutoGuestLogin = useCallback(() => {
      if (typeof window === 'undefined') {
        return false;
      }
      const params = new URLSearchParams(window.location.search);
      return (
        params.get('admin') === '1' ||
        sessionStorage.getItem(SUPPRESS_AUTO_GUEST_LOGIN_KEY) === '1'
      );
    }, []);

    const switchToAdminLogin = useCallback(() => {
      sessionStorage.setItem(SUPPRESS_AUTO_GUEST_LOGIN_KEY, '1');
      clearTokenState();
    }, [clearTokenState]);

    const tryAutoGuestSession = useCallback(async () => {
      if (shouldSuppressAutoGuestLogin()) {
        return false;
      }
      try {
        const kioskStatus = await fetchConventionKioskStatus();
        if (!kioskStatus?.convention_mode || !kioskStatus?.kiosk_mode) {
          return false;
        }

        const tokenPayload = await fetchConventionGuestToken();
        if (!tokenPayload?.access_token) {
          return false;
        }
        setGuestToken(tokenPayload.access_token);
        return true;
      } catch (error) {
        return false;
      }
    }, [setGuestToken, shouldSuppressAutoGuestLogin]);

    const logout = useCallback(async () => {
        clearTokenState();
        await tryAutoGuestSession();
    }, [clearTokenState, tryAutoGuestSession]);

    const fetchUser = useCallback(async () => {
        setLoading(true);
        if (token) {
            setAuthToken(token);
            try {
                const currentUser = await fetchCurrentUser();
                setUser(currentUser);
                if (!currentUser?.is_guest) {
                  sessionStorage.removeItem(SUPPRESS_AUTO_GUEST_LOGIN_KEY);
                }
            } catch (error) {
                console.error('Failed to fetch user', error);
                clearTokenState();
            }
        } else {
            const startedGuestSession = await tryAutoGuestSession();
            if (!startedGuestSession) {
                setUser(null);
            }
        }
        setLoading(false);
    }, [token, clearTokenState, tryAutoGuestSession]);

    useEffect(() => {
        fetchUser();
    }, [fetchUser]);

    const login = useCallback(async (username, password) => {
        try {
        const { access_token } = await loginWithPassword(username, password);
        setUserToken(access_token);
        const currentUser = await fetchCurrentUser();
        setUser(currentUser);
        if (!currentUser?.is_guest) {
          sessionStorage.removeItem(SUPPRESS_AUTO_GUEST_LOGIN_KEY);
        }
        } catch (error) {
            console.error('Login failed:', error);
            throw error;
        }
    }, [setUserToken]);

    return (
        <AuthContext.Provider value={{ user, token, login, logout, switchToAdminLogin, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export default AuthContext; 
