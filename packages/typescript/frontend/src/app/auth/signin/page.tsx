"use client"

import React from 'react';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { loginWithPassword, oauthStartUrl, persistSessionToken } from '@/utils/backendAuth';
import { useAppSession } from '@/contexts/AppSessionContext';

export default function SigninPage() {
  const [error, setError] = useState<string | null>(null);
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: ''
  });
  const router = useRouter();
  const { refreshSession } = useAppSession();
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoginMode) {
      await handleLogin(formData.email, formData.password);
    } else {
      await handleRegister(formData.email, formData.password, formData.name);
    }
  };

  const handleLogin = async (email: string, password: string) => {
    try {
      setError(null);
      const result = await loginWithPassword(email, password);
      await persistSessionToken(result.token);
      await refreshSession();
      router.refresh();
      router.push('/dashboard');
    } catch (loginError) {
      console.error('Login error:', loginError);
      setError(loginError instanceof Error ? loginError.message : 'Login failed. Please try again.');
    }
  };

  const handleRegister = async (email: string, password: string, name: string) => {
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name }),
      });

      const data = await response.json();
      
      if (response.ok) {
        setError(null);
        setSuccessMessage(data.message || 'Registration successful. Please check your email to verify your account.');
        setIsLoginMode(true);
      } else {
        throw new Error(data.error || 'Registration failed');
      }
    } catch (registerError) {
      console.error('Registration error:', registerError);
      setError(registerError instanceof Error ? registerError.message : 'Registration failed');
    }
  };

  const handleSocialLogin = (provider: 'google' | 'github') => {
    window.location.href = oauthStartUrl(provider, '/dashboard');
  };

  return (
    <div className="flex flex-col items-center mt-8 px-4">
      <h1 className="text-2xl font-semibold mb-6">
        {isLoginMode ? 'Sign In' : 'Register'}
      </h1>
      
      {error && (
        <div className="text-red-500 mb-4">
          {error}
        </div>
      )}
      
      {successMessage && (
        <div className="text-green-500 mb-4">
          {successMessage}
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-2">
        {!isLoginMode && (
          <input
            type="text"
            id="name"
            name="name"
            placeholder="Name"
            value={formData.name}
            onChange={handleInputChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder-gray-400"
            required
          />
        )}

        <input
          type={isLoginMode ? "text" : "email"}
          id="email"
          name="email"
          placeholder="Email"
          value={formData.email}
          onChange={handleInputChange}
          autoComplete={isLoginMode ? "username" : "email"}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder-gray-400"
          required
        />

        <div className="relative">
          <input
            type="password"
            id="password"
            name="password"
            value={formData.password}
            onChange={handleInputChange}
            placeholder="Password"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder-gray-400"
            required
          />
        </div>

        <button
          type="submit"
          className="w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
        >
          {isLoginMode ? 'Sign In' : 'Register'}
        </button>

        <div className="text-center text-sm">
          <button
            type="button"
            onClick={() => setIsLoginMode(!isLoginMode)}
            className="text-blue-600 hover:text-blue-800 focus:outline-none"
          >
            {isLoginMode ? "Don't have an account? Register" : 'Already have an account? Sign in'}
          </button>
        </div>
      </form>

      <div className="w-full max-w-sm my-6 flex items-center">
        <div className="flex-grow border-t border-gray-300"></div>
        <span className="px-4 text-gray-500 text-sm">Or</span>
        <div className="flex-grow border-t border-gray-300"></div>
      </div>

      <div className="flex flex-col gap-3 w-full max-w-sm">
        <button
          onClick={() => handleSocialLogin('google')}
          className="flex items-center justify-center gap-2 w-full px-4 py-2 text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
        >
          Sign in with Google
        </button>

        <button
          onClick={() => handleSocialLogin('github')}
          className="flex items-center justify-center gap-2 w-full px-4 py-2 text-white bg-gray-800 hover:bg-gray-900 rounded-md transition-colors"
        >
          Sign in with GitHub
        </button>
      </div>
    </div>
  );
}
