import { useState } from 'react';
import { signOut } from 'next-auth/react';
import { toastActionError } from '@/utils/toastActionError';

interface DeleteAccountModalProps {
    open: boolean;
    onClose: () => void;
}

export default function DeleteAccountModal({ open, onClose }: DeleteAccountModalProps) {
    const [loading, setLoading] = useState(false);

    const handleDelete = async () => {
        try {
            setLoading(true);

            const response = await fetch('/api/user/account', {
                method: 'DELETE',
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to delete account');
            }

            await signOut({ callbackUrl: '/auth/signin' });
        } catch (err) {
            console.error('Failed to delete account:', err);
            toastActionError('Failed to delete account', err);
            setLoading(false);
        }
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
                <div className="p-6">
                    <h2 className="text-xl font-semibold text-red-500 mb-4">
                        Delete Account
                    </h2>

                    <div className="space-y-4">
                        <p className="text-gray-700">
                            Are you sure you want to delete your account? This action cannot be undone.
                        </p>
                        <p className="text-gray-700">
                            All your data will be permanently deleted.
                        </p>
                    </div>
                </div>

                <div className="flex justify-end gap-3 px-6 py-4 bg-gray-50 rounded-b-lg">
                    <button
                        type="button"
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md"
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        onClick={handleDelete}
                        disabled={loading}
                        className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? 'Deleting...' : 'Delete Account'}
                    </button>
                </div>
            </div>
        </div>
    );
} 