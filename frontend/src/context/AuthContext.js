import React, { createContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { apiBaseUrl } from '../config';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(() => localStorage.getItem('token'));
    const [loading, setLoading] = useState(true);

    const logout = useCallback(() => {
        setUser(null);
        setToken(null);
        localStorage.removeItem('token');
        delete axios.defaults.headers.common['Authorization'];
    }, []);

    const fetchUser = useCallback(async () => {
        if (token) {
            axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
            try {
                const response = await axios.get(`${apiBaseUrl}/users/me/`);
                setUser(response.data);
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
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        
            const response = await axios.post(`${apiBaseUrl}/token`, formData);
        const { access_token } = response.data;
        
        setToken(access_token);
        localStorage.setItem('token', access_token);
        axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
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