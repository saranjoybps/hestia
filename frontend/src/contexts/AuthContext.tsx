'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { User, onAuthStateChanged, signInWithEmailAndPassword, signOut } from 'firebase/auth';
import { auth } from '@/lib/firebase';
import apiClient from '@/lib/api';

interface UserData {
  uid: string;
  email: string;
  name: string;
  role: 'employee' | 'lead' | 'manager' | 'hr' | 'director' | 'super_admin';
  department?: string;
  designation?: string;
  phone?: string;
  dateOfJoining?: string;
  status: 'active' | 'inactive';
  manager_id?: string;
  lead_id?: string;
  managerId?: string;
  leadId?: string;
  reportees?: string[];
}

interface AuthContextType {
  user: User | null;
  userData: UserData | null;
  loading: boolean;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [userData, setUserData] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      
      if (firebaseUser) {
        try {
          // Get ID token and store it
          const token = await firebaseUser.getIdToken();
          localStorage.setItem('authToken', token);
          
          // Fetch user data from backend
          const response = await apiClient.get('/users/me');
          setUserData(response.data);
        } catch (error) {
          console.error('Error fetching user data:', error);
          setUserData(null);
        }
      } else {
        localStorage.removeItem('authToken');
        setUserData(null);
      }
      
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const createAuditLog = async (
    token: string,
    payload: {
      module?: string;
      action: string;
      description?: string;
      result?: string;
      target_type?: string;
      target_id?: string;
      metadata?: Record<string, any>;
    }
  ) => {
    try {
      await apiClient.post(
        '/audit-logs',
        payload,
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } catch (error) {
      console.warn('Audit log failed:', error);
    }
  };

  const login = async (email: string, password: string, rememberMe: boolean = false) => {
    try {
      const userCredential = await signInWithEmailAndPassword(auth, email, password);
      const token = await userCredential.user.getIdToken();
      
      if (rememberMe) {
        localStorage.setItem('authToken', token);
      } else {
        sessionStorage.setItem('authToken', token);
      }

      await createAuditLog(token, {
        module: 'auth',
        action: 'login',
        description: 'User logged in',
        result: 'success',
        target_type: 'auth',
        target_id: userCredential.user.uid,
        metadata: { remember_me: rememberMe }
      });
    } catch (error: any) {
      console.error('Login error:', error);
      throw new Error(error.message || 'Failed to login');
    }
  };

  const logout = async () => {
    try {
      const token = await user?.getIdToken();
      if (token && user?.uid) {
        await createAuditLog(token, {
          module: 'auth',
          action: 'logout',
          description: 'User logged out',
          result: 'success',
          target_type: 'auth',
          target_id: user.uid
        });
      }
      await signOut(auth);
      localStorage.removeItem('authToken');
      sessionStorage.removeItem('authToken');
      setUserData(null);
    } catch (error: any) {
      console.error('Logout error:', error);
      throw new Error(error.message || 'Failed to logout');
    }
  };

  const hasRole = (...roles: string[]) => {
    if (!userData) return false;
    const role = userData.role.toLowerCase();
    return roles.some(r => r.toLowerCase() === role);
  };

  const value: AuthContextType = {
    user,
    userData,
    loading,
    login,
    logout,
    hasRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
