import React, { createContext, useState, useEffect, useCallback } from 'react';
import { fetchConventionGuestToken, fetchCurrentUser, loginWithPassword } from '../api/auth';
import { fetchConventionKioskStatus } from '../api/convention';
import { clearAuthToken, setAuthToken } from '../api/client';

const AuthContext = createContext();
const USER_TOKEN_STORAGE_KEY = 'token';
const GUEST_TOKEN_STORAGE_KEY = 'guest_token';
const SUPPRESS_AUTO_GUEST_LOGIN_KEY = 'suppress_auto_guest_login';
const GUEST_INACTIVITY_TIMEOUT_MS = 5 * 60 * 1000;
const RECOMMENDATION_STATE_STORAGE_PREFIX = 'game_list_recommendation_state_v1';
const NON_LIBRARY_NOTICE_SESSION_KEY = 'hasSeenNonLibraryMessage';

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(
      () => localStorage.getItem(USER_TOKEN_STORAGE_KEY) || sessionStorage.getItem(GUEST_TOKEN_STORAGE_KEY)
    );
    const [loading, setLoading] = useState(true);
    const [kioskUnavailable, setKioskUnavailable] = useState(false);
    const [kioskUnavailableReason, setKioskUnavailableReason] = useState('');

    const clearTokenState = useCallback(() => {
        setUser(null);
        setToken(null);
        localStorage.removeItem(USER_TOKEN_STORAGE_KEY);
        sessionStorage.removeItem(GUEST_TOKEN_STORAGE_KEY);
        clearAuthToken();
    }, []);

    const clearGuestSessionState = useCallback(() => {
      try {
        const keysToRemove = [];
        for (let index = 0; index < window.sessionStorage.length; index += 1) {
          const key = window.sessionStorage.key(index);
          if (!key) {
            continue;
          }
          if (
            key === GUEST_TOKEN_STORAGE_KEY ||
            key === NON_LIBRARY_NOTICE_SESSION_KEY ||
            key.startsWith(`${RECOMMENDATION_STATE_STORAGE_PREFIX}:`)
          ) {
            keysToRemove.push(key);
          }
        }
        keysToRemove.forEach((key) => window.sessionStorage.removeItem(key));
      } catch (_error) {
        // Best-effort cleanup.
      }
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
        setKioskUnavailable(false);
        setKioskUnavailableReason('');
        return false;
      }
      try {
        const kioskStatus = await fetchConventionKioskStatus();
        if (!kioskStatus?.convention_mode || !kioskStatus?.kiosk_mode) {
          setKioskUnavailable(false);
          setKioskUnavailableReason('');
          return false;
        }

        const tokenPayload = await fetchConventionGuestToken();
        if (!tokenPayload?.access_token) {
          setKioskUnavailable(true);
          setKioskUnavailableReason('guest_token_missing');
          return false;
        }
        setGuestToken(tokenPayload.access_token);
        setKioskUnavailable(false);
        setKioskUnavailableReason('');
        return true;
      } catch (error) {
        setKioskUnavailable(true);
        setKioskUnavailableReason(
          error?.response?.data?.detail || error?.message || 'guest_token_failed'
        );
        return false;
      }
    }, [setGuestToken, shouldSuppressAutoGuestLogin]);

    const retryGuestSessionBootstrap = useCallback(async () => {
      await tryAutoGuestSession();
    }, [tryAutoGuestSession]);

    const logout = useCallback(async () => {
        if (user?.is_guest) {
          clearGuestSessionState();
        }
        clearTokenState();
        await tryAutoGuestSession();
    }, [clearGuestSessionState, clearTokenState, tryAutoGuestSession, user]);

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
                setKioskUnavailable(false);
                setKioskUnavailableReason('');
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

    useEffect(() => {
      if (!user?.is_guest) {
        return undefined;
      }

      let inactivityTimer = null;

      const resetInactivityTimer = () => {
        if (inactivityTimer) {
          window.clearTimeout(inactivityTimer);
        }
        inactivityTimer = window.setTimeout(() => {
          logout();
        }, GUEST_INACTIVITY_TIMEOUT_MS);
      };

      const activityEvents = ['pointerdown', 'keydown', 'touchstart', 'mousemove', 'scroll'];
      activityEvents.forEach((eventName) => {
        window.addEventListener(eventName, resetInactivityTimer, { passive: true });
      });
      resetInactivityTimer();

      return () => {
        if (inactivityTimer) {
          window.clearTimeout(inactivityTimer);
        }
        activityEvents.forEach((eventName) => {
          window.removeEventListener(eventName, resetInactivityTimer);
        });
      };
    }, [logout, user]);

    const login = useCallback(async (username, password) => {
        try {
        const { access_token } = await loginWithPassword(username, password);
        setUserToken(access_token);
        const currentUser = await fetchCurrentUser();
        setUser(currentUser);
        if (!currentUser?.is_guest) {
          sessionStorage.removeItem(SUPPRESS_AUTO_GUEST_LOGIN_KEY);
        }
        setKioskUnavailable(false);
        setKioskUnavailableReason('');
        } catch (error) {
            console.error('Login failed:', error);
            throw error;
        }
    }, [setUserToken]);

    return (
        <AuthContext.Provider
          value={{
            user,
            token,
            login,
            logout,
            switchToAdminLogin,
            retryGuestSessionBootstrap,
            kioskUnavailable,
            kioskUnavailableReason,
            loading,
          }}
        >
            {children}
        </AuthContext.Provider>
    );
};

export default AuthContext; 
