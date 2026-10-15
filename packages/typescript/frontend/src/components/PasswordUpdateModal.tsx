import { useState } from 'react';
import { toastActionError } from '@/utils/toastActionError';

interface PasswordUpdateModalProps {
    open: boolean;
    onClose: () => void;
    onUpdate: (oldPassword: string, newPassword: string) => Promise<void>;
}

export default function PasswordUpdateModal({ open, onClose, onUpdate }: PasswordUpdateModalProps) {
    const [oldPassword, setOldPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        if (newPassword !== confirmPassword) {
            setError("New passwords don't match");
            return;
        }

        if (newPassword.length < 8) {
            setError("New password must be at least 8 characters long");
            return;
        }

        try {
            setLoading(true);
            await onUpdate(oldPassword, newPassword);
            onClose();
        } catch (err) {
            console.error('Failed to update password:', err);
            toastActionError('Failed to update password', err);
        } finally {
            setLoading(false);
        }
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
                <form onSubmit={handleSubmit}>
                    <div className="p-6">
                        <h2 className="text-xl font-semibold mb-4">
                            Update Password
                        </h2>

                        {error && (
                            <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md">
                                {error}
                            </div>
                        )}

                        <div className="mb-6">
                            <h3 className="text-sm font-medium mb-1">Password Requirements:</h3>
                            <p className="text-sm">• Minimum 8 characters long</p>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium mb-1" htmlFor="current-password">
                                    Current Password
                                </label>
                                <input
                                    id="current-password"
                                    type="password"
                                    value={oldPassword}
                                    onChange={(e) => setOldPassword(e.target.value)}
                                    className="w-full px-3 py-2 border rounded-md bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    placeholder="Enter your current password"
                                    required
                                    autoFocus
                                />
                                <p className="mt-1 text-sm text-gray-500">
                                    Enter your current password for verification
                                </p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1" htmlFor="new-password">
                                    New Password
                                </label>
                                <input
                                    id="new-password"
                                    type="password"
                                    value={newPassword}
                                    onChange={(e) => setNewPassword(e.target.value)}
                                    className="w-full px-3 py-2 border rounded-md bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    placeholder="Enter your new password"
                                    required
                                />
                                <p className="mt-1 text-sm text-gray-500">
                                    Enter your desired new password (minimum 8 characters)
                                </p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1" htmlFor="confirm-password">
                                    Confirm New Password
                                </label>
                                <input
                                    id="confirm-password"
                                    type="password"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    className="w-full px-3 py-2 border rounded-md bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    placeholder="Re-enter your new password"
                                    required
                                />
                                <p className="mt-1 text-sm text-gray-500">
                                    Re-enter your new password to confirm
                                </p>
                            </div>
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
                            type="submit"
                            disabled={loading}
                            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loading ? 'Updating...' : 'Update Password'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
} 