import { useEffect, useState } from "react";
import { Trash2, UserPlus, Users } from "lucide-react";
import { api, ApiError } from "@/api/client";
import type { UserRecord, UserRole } from "@/api/types";
export default function AdminTab() {
    const [users, setUsers] = useState<UserRecord[]>([]);
    const [newUser, setNewUser] = useState("");
    const [newRole, setNewRole] = useState<UserRole>("user");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        fetchUsers();
    }, []);

    async function fetchUsers() {
        try {
            setUsers(await api.getUsers());
            setError("");
        } catch (caught) {
            setError(apiErrorMessage(caught, "Failed to load users"));
        }
    }

    async function addUser(e: React.FormEvent) {
        e.preventDefault();
        if (!newUser.trim()) return;
        setLoading(true);
        try {
            const data = await api.addUser(newUser.trim(), newRole);
            setUsers(data.users);
            setNewUser("");
            setNewRole("user");
            setError("");
        } catch (caught) {
            setError(apiErrorMessage(caught, "Error adding user"));
        } finally {
            setLoading(false);
        }
    }

    async function removeUser(username: string) {
        if (!confirm(`Are you sure you want to remove ${username}?`)) return;
        setLoading(true);
        try {
            const data = await api.removeUser(username);
            setUsers(data.users);
            setError("");
        } catch (caught) {
            setError(apiErrorMessage(caught, "Error removing user"));
        } finally {
            setLoading(false);
        }
    }

    async function updateRole(username: string, role: UserRole) {
        setLoading(true);
        try {
            const data = await api.updateUser(username, role);
            setUsers(data.users);
            setError("");
        } catch (caught) {
            setError(apiErrorMessage(caught, "Error updating role"));
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="space-y-6">
            <div className="bg-white p-6 rounded-2xl border shadow-sm">
                <div className="flex items-center gap-4 mb-6">
                    <div className="size-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                        <Users size={20} />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold">User Whitelist & Roles</h2>
                        <p className="text-sm text-slate-500">Manage who can access the dashboard and their permissions.</p>
                    </div>
                </div>

                {/* Add User Form */}
                <form onSubmit={addUser} className="flex gap-3 items-end mb-8 bg-slate-50 p-4 rounded-xl border">
                    <div className="flex-1 space-y-1">
                        <label className="text-sm font-medium text-slate-700">Add New User</label>
                        <div className="relative">
                            <UserPlus className="absolute left-3 top-2.5 text-slate-400" size={16} />
                            <input
                                type="text"
                                placeholder="username (e.g. jdoe)"
                                value={newUser}
                                onChange={(e) => setNewUser(e.target.value)}
                                className="pl-9 flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                    </div>

                    <div className="w-32 space-y-1">
                        <label className="text-sm font-medium text-slate-700">Role</label>
                        <select
                            value={newRole}
                            onChange={(e) => setNewRole(e.target.value as UserRole)}
                            className="flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                            <option value="user">User</option>
                            <option value="admin">Admin</option>
                        </select>
                    </div>

                    <button
                        type="submit"
                        disabled={loading || !newUser.trim()}
                        className="h-10 px-4 py-2 bg-slate-900 text-white rounded-md text-sm font-medium hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? "Adding..." : "Add"}
                    </button>
                </form>

                {error && <div className="text-red-500 text-sm mb-4">{error}</div>}

                {/* Users List */}
                <div className="border rounded-xl overflow-hidden">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50 border-b">
                            <tr>
                                <th className="px-4 py-3 font-medium text-slate-700">Username</th>
                                <th className="px-4 py-3 font-medium text-slate-700">Role</th>
                                <th className="px-4 py-3 font-medium text-slate-700 w-24 text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y">
                            {users.map((u) => (
                                <tr key={u.username} className="bg-white hover:bg-slate-50">
                                    <td className="px-4 py-3 font-medium">{u.username}</td>
                                    <td className="px-4 py-3">
                                        <select
                                            value={u.role}
                                            disabled={loading}
                                            onChange={(event) => void updateRole(u.username, event.target.value as UserRole)}
                                            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs disabled:opacity-50"
                                            aria-label={`Role for ${u.username}`}
                                        >
                                            <option value="user">User</option>
                                            <option value="admin">Admin</option>
                                        </select>
                                    </td>
                                    <td className="px-4 py-3 text-center">
                                        <button
                                            onClick={() => removeUser(u.username)}
                                            disabled={loading}
                                            className="p-2 text-slate-400 hover:text-red-600 transition-colors rounded-md hover:bg-red-50"
                                            title="Remove user"
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {users.length === 0 && (
                                <tr>
                                    <td colSpan={3} className="px-4 py-8 text-center text-slate-500">
                                        No users in whitelist.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}


function apiErrorMessage(error: unknown, fallback: string): string {
    return error instanceof ApiError ? error.message : fallback;
}
