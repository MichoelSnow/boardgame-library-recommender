import React, { createContext, useState, useEffect, useCallback } from 'react';
import { fetchCurrentUser, loginWithPassword } from '../api/auth';
import { clearAuthToken, setAuthToken } from '../api/client';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(() => localStorage.getItem('token'));
    const [loading, setLoading] = useState(true);

    const logout = useCallback(() => {
        setUser(null);
        setToken(null);
        localStorage.removeItem('token');
        clearAuthToken();
    }, []);

    const fetchUser = useCallback(async () => {
        if (token) {
            setAuthToken(token);
            try {
                const currentUser = await fetchCurrentUser();
                setUser(currentUser);
            } catch (error) {
                console.error('Failed to fetch user', error);
                logout();
            }
        }
        setLoading(false);
    }, [token, logout]);

    useEffect(() => {
        fetchUser();
    }, [fetchUser]);

    const login = useCallback(async (username, password) => {
        try {
        const { access_token } = await loginWithPassword(username, password);
        
        setToken(access_token);
        localStorage.setItem('token', access_token);
        setAuthToken(access_token);
        await fetchUser();
        } catch (error) {
            console.error('Login failed:', error);
            throw error;
        }
    }, [fetchUser]);

    return (
        <AuthContext.Provider value={{ user, token, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export default AuthContext; 
