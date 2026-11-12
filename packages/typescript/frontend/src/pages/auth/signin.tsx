"use client";

import React, { useState } from 'react';
import { useRouter, useSearchParams } from '@/utils/appRouter';
import { loginWithPassword, oauthStartUrl, persistSessionToken, registerWithPassword } from '@/utils/backendAuth';
import { useAppSession } from '@/contexts/AppSessionContext';
import { appName } from '@/config/branding';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldGroup, FieldLabel, FieldSeparator } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

export default function SigninPage() {
  const [error, setError] = useState<string | null>(null);
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: '',
  });
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = (() => {
    const from = searchParams.get('from') || searchParams.get('callbackUrl');
    return from && from.startsWith('/') && !from.startsWith('//') ? from : '/dashboard';
  })();
  const { refreshSession } = useAppSession();
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
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
      router.replace(returnTo);
    } catch (loginError) {
      console.error('Login error:', loginError);
      setError(loginError instanceof Error ? loginError.message : 'Login failed. Please try again.');
    }
  };

  const handleRegister = async (email: string, password: string, name: string) => {
    try {
      setError(null);
      const data = await registerWithPassword(email, password, name);
      setSuccessMessage(
        data.message || 'Registration successful. Please check your email to verify your account.',
      );
      setIsLoginMode(true);
    } catch (registerError) {
      console.error('Registration error:', registerError);
      setError(registerError instanceof Error ? registerError.message : 'Registration failed');
    }
  };

  const handleSocialLogin = (provider: 'google' | 'github') => {
    window.location.href = oauthStartUrl(provider, returnTo);
  };

  return (
    <div className="flex min-h-full flex-col md:flex-row">
      <aside className="flex flex-col justify-between gap-8 bg-brand p-8 text-brand-foreground md:w-5/12 md:p-12">
        <div />
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold md:text-4xl">{appName}</h1>
          <p className="text-brand-foreground/90">AI-powered document processing for your ERP.</p>
        </div>
        <p className="hidden text-sm text-brand-foreground/80 md:block">
          &copy; {new Date().getFullYear()} {appName}
        </p>
      </aside>

      <main className="flex flex-1 items-center justify-center p-6">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{isLoginMode ? 'Sign in' : 'Register'}</CardTitle>
            <CardDescription>
              {isLoginMode ? 'Use your email and password, or a connected account.' : 'Create an account to get started.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {error ? (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            {successMessage ? (
              <Alert variant="success">
                <AlertDescription>{successMessage}</AlertDescription>
              </Alert>
            ) : null}

            <form onSubmit={handleSubmit} noValidate>
              <FieldGroup>
                {!isLoginMode ? (
                  <Field>
                    <FieldLabel htmlFor="name">Name</FieldLabel>
                    <Input
                      id="name"
                      name="name"
                      value={formData.name}
                      onChange={handleInputChange}
                      autoComplete="name"
                      required
                    />
                  </Field>
                ) : null}
                <Field>
                  <FieldLabel htmlFor="email">Email</FieldLabel>
                  <Input
                    id="email"
                    name="email"
                    type={isLoginMode ? 'text' : 'email'}
                    autoComplete={isLoginMode ? 'username' : 'email'}
                    value={formData.email}
                    onChange={handleInputChange}
                    required
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="password">Password</FieldLabel>
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    autoComplete={isLoginMode ? 'current-password' : 'new-password'}
                    value={formData.password}
                    onChange={handleInputChange}
                    required
                  />
                </Field>
                <Button type="submit" className="w-full">
                  {isLoginMode ? 'Sign in' : 'Register'}
                </Button>
                <Button
                  type="button"
                  variant="link"
                  className="w-full"
                  onClick={() => {
                    setIsLoginMode(!isLoginMode);
                    setError(null);
                    setSuccessMessage(null);
                  }}
                >
                  {isLoginMode ? "Don't have an account? Register" : 'Already have an account? Sign in'}
                </Button>
              </FieldGroup>
            </form>

            <FieldSeparator>Or</FieldSeparator>

            <div className="flex flex-col gap-2">
              <Button type="button" onClick={() => handleSocialLogin('google')}>
                Sign in with Google
              </Button>
              <button
                type="button"
                onClick={() => handleSocialLogin('github')}
                className={cn(buttonVariants({ variant: 'outline' }), 'w-full')}
              >
                Sign in with GitHub
              </button>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
