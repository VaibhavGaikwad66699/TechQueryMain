import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../services/api';
import { User, UserPreference } from '../types';

interface AuthContextType {
  user: User | null;
  preferences: UserPreference;
  loading: boolean;
  login: (data: { email: string; password: string }) => Promise<void>;
  register: (data: { email: string; username: string; password: string }) => Promise<void>;
  logout: () => void;
  updatePreferences: (prefs: Partial<UserPreference>) => Promise<void>;
  refreshUser: () => Promise<void>;
  refreshPreferences: () => Promise<void>;
}

const defaultPreferences: UserPreference = {
  explanation_level: 'Intermediate',
  answer_style: 'Detailed',
  include_examples: true,
  preferred_subject: 'All',
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [preferences, setPreferences] = useState<UserPreference>(defaultPreferences);
  const [loading, setLoading] = useState<boolean>(true);
  const sessionVersion = useRef(0);

  const fetchUserData = async () => {
    const version = ++sessionVersion.current;
    try {
      if (api.getToken()) {
        const currentUser = await api.getCurrentUser();
        if (version !== sessionVersion.current) return;
        setUser(currentUser);
        try {
          const userPrefs = await api.getPreferences();
          if (version === sessionVersion.current) setPreferences(userPrefs);
        } catch {
          // fallback to defaults if preferences fail
        }
      } else {
        setUser(null);
      }
    } catch (error) {
      if (version !== sessionVersion.current) return;
      // A sleeping/restarting host is not evidence that a JWT is invalid.
      if (error instanceof ApiError && error.status === 401) api.setToken(null);
      setUser(null);
      setPreferences(defaultPreferences);
    } finally {
      if (version === sessionVersion.current) setLoading(false);
    }
  };

  useEffect(() => {
    fetchUserData();
  }, []);

  const login = async (data: { email: string; password: string }) => {
    const version = ++sessionVersion.current;
    const res = await api.login(data);
    if (version !== sessionVersion.current) return;
    setPreferences(defaultPreferences);
    setUser(res.user);
    try {
      const prefs = await api.getPreferences();
      if (version === sessionVersion.current) setPreferences(prefs);
    } catch {
      if (version === sessionVersion.current) setPreferences(defaultPreferences);
    }
  };

  const register = async (data: { email: string; username: string; password: string }) => {
    const version = ++sessionVersion.current;
    const res = await api.register(data);
    if (version !== sessionVersion.current) return;
    setPreferences(defaultPreferences);
    setUser(res.user);
    try {
      const prefs = await api.getPreferences();
      if (version === sessionVersion.current) setPreferences(prefs);
    } catch {
      if (version === sessionVersion.current) setPreferences(defaultPreferences);
    }
  };

  const logout = () => {
    sessionVersion.current++;
    api.setToken(null);
    setUser(null);
    setPreferences(defaultPreferences);
  };

  const updatePreferences = async (newPrefs: Partial<UserPreference>) => {
    const version = sessionVersion.current;
    if (user) {
      const updated = await api.updatePreferences(newPrefs);
      if (version === sessionVersion.current) setPreferences(updated);
    } else {
      setPreferences(prev => ({ ...prev, ...newPrefs }));
    }
  };

  const refreshUser = async () => {
    await fetchUserData();
  };

  const refreshPreferences = async () => {
    const version = sessionVersion.current;
    const updated = await api.getPreferences();
    if (version === sessionVersion.current) setPreferences(updated);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        preferences,
        loading,
        login,
        register,
        logout,
        updatePreferences,
        refreshUser,
        refreshPreferences,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
