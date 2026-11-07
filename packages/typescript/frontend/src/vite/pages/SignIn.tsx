import { useState, type ChangeEvent, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  loginWithPassword,
  oauthStartUrl,
  persistSessionToken,
  registerWithPassword,
} from '@/utils/backendAuth';
import { useAppSession } from '@/contexts/AppSessionContext';

/** Vite route — same flows as Next `auth/signin` without `next/navigation`. */
export function SignInPage() {
  const navigate = useNavigate();
  const { refreshSession } = useAppSession();
  const [error, setError] = useState<string | null>(null);
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [formData, setFormData] = useState({ email: '', password: '', name: '' });

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleLogin = async (email: string, password: string) => {
    try {
      setError(null);
      const result = await loginWithPassword(email, password);
      await persistSessionToken(result.token);
      await refreshSession();
      navigate('/', { replace: true });
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : 'Login failed. Please try again.');
    }
  };

  const handleRegister = async (email: string, password: string, name: string) => {
    try {
      setError(null);
      setSuccessMessage(null);
      const result = await registerWithPassword(email, password, name);
      setSuccessMessage(result.message);
      setIsLoginMode(true);
    } catch (registerError) {
      setError(registerError instanceof Error ? registerError.message : 'Registration failed.');
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (isLoginMode) {
      await handleLogin(formData.email, formData.password);
    } else {
      await handleRegister(formData.email, formData.password, formData.name);
    }
  };

  return (
    <main className="max-w-md mx-auto mt-12 p-6">
      <p className="mb-4 text-sm">
        <Link className="text-blue-600 hover:underline" to="/">
          ← Home
        </Link>
      </p>
      <h1 className="text-2xl font-semibold mb-6">{isLoginMode ? 'Sign in' : 'Register'}</h1>
      {error && <p className="text-red-600 text-sm mb-4">{error}</p>}
      {successMessage && <p className="text-green-700 text-sm mb-4">{successMessage}</p>}
      <form onSubmit={handleSubmit} className="space-y-4">
        {!isLoginMode && (
          <input
            name="name"
            placeholder="Name"
            value={formData.name}
            onChange={handleInputChange}
            className="w-full border rounded px-3 py-2"
            required
          />
        )}
        <input
          name="email"
          type="email"
          placeholder="Email"
          value={formData.email}
          onChange={handleInputChange}
          className="w-full border rounded px-3 py-2"
          required
        />
        <input
          name="password"
          type="password"
          placeholder="Password"
          value={formData.password}
          onChange={handleInputChange}
          className="w-full border rounded px-3 py-2"
          required
        />
        <button type="submit" className="w-full bg-blue-600 text-white rounded py-2">
          {isLoginMode ? 'Sign in' : 'Register'}
        </button>
      </form>
      <button
        type="button"
        className="mt-4 text-sm text-blue-600"
        onClick={() => {
          setIsLoginMode(!isLoginMode);
          setError(null);
        }}
      >
        {isLoginMode ? 'Create an account' : 'Back to sign in'}
      </button>
      <div className="mt-6 flex flex-col gap-2 text-sm">
        <a className="text-blue-600 hover:underline" href={oauthStartUrl('google', '/')}>
          Sign in with Google
        </a>
        <a className="text-blue-600 hover:underline" href={oauthStartUrl('github', '/')}>
          Sign in with GitHub
        </a>
      </div>
    </main>
  );
}
