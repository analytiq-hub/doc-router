'use client'

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { verifyEmailApi } from '@/utils/api';
import { useSession } from 'next-auth/react';

export default function VerifyEmailPage() {
  const [status, setStatus] = useState<'verifying' | 'success' | 'error'>('verifying');
  const [error, setError] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const router = useRouter();
  const { data: session } = useSession();

  useEffect(() => {
    const verifyEmail = async () => {
      const token = searchParams.get('token');
      if (!token) {
        setStatus('error');
        setError('Invalid verification link');
        return;
      }

      try {
        console.log(`Verifying email with token: ${token}`);
        await verifyEmailApi(token);
        setStatus('success');
        // Only redirect to signin if user is not already logged in
        setTimeout(() => {
          if (!session) {
            router.push('/auth/signin');
          } else {
            router.push('/');
          }
        }, 3000);
      } catch (error) {
        console.error(`Failed to verify email: ${error}`);
        setStatus('error');
        setError('Failed to verify email. The link may be expired or invalid.');
      }
    };

    verifyEmail();
  }, [searchParams, router, session]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold text-gray-900 mb-4">
            Email Verification
          </h2>
          
          {status === 'verifying' && (
            <div className="text-gray-600">
              Verifying your email address...
            </div>
          )}

          {status === 'success' && (
            <div className="text-green-600">
              Your email has been verified successfully!
              <p className="text-sm mt-2">
                Redirecting to {session ? 'homepage' : 'signin page'}...
              </p>
            </div>
          )}

          {status === 'error' && (
            <div className="text-red-600">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 