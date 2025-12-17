import { useEffect, useState } from "react";
import { Trash2, UserPlus, Users } from "lucide-react";

// Minimal UI components (inline or imported if available, but for safety using Tailwind directly for layout)
// Assuming Card/Button are available or we simulate them.
// To be safe and consistent with previous code I've seen, I'll use standard Tailwind elements that look like the existing design.

export default function AdminTab() {
    const [users, setUsers] = useState<string[]>([]);
    const [newUser, setNewUser] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        fetchUsers();
    }, []);

    async function fetchUsers() {
        try {
            const res = await fetch("/api/users");
            if (res.ok) {
                const data = await res.json();
                setUsers(data);
            }
        } catch (err) {
            console.error("Failed to fetch users", err);
        }
    }

    async function addUser(e: React.FormEvent) {
        e.preventDefault();
        if (!newUser.trim()) return;
        setLoading(true);
        try {
            const res = await fetch("/api/users/add", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: newUser.trim() }),
            });
            if (res.ok) {
                const data = await res.json();
                setUsers(data.users);
                setNewUser("");
                setError("");
            } else {
                setError("Failed to add user");
            }
        } catch (err) {
            setError("Error adding user");
        } finally {
            setLoading(false);
        }
    }

    async function removeUser(username: string) {
        if (!confirm(`Are you sure you want to remove ${username}?`)) return;
        try {
            const res = await fetch("/api/users/remove", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username }),
            });
            if (res.ok) {
                const data = await res.json();
                setUsers(data.users);
            }
        } catch (err) {
            console.error("Error removing user", err);
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
                        <h2 className="text-lg font-semibold">User Whitelist</h2>
                        <p className="text-sm text-slate-500">Manage who can access the Gyrotron Control dashboard.</p>
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
                                placeholder="username (e.g. gemond)"
                                value={newUser}
                                onChange={(e) => setNewUser(e.target.value)}
                                className="pl-9 flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                    </div>
                    <button
                        type="submit"
                        disabled={loading || !newUser.trim()}
                        className="h-10 px-4 py-2 bg-slate-900 text-white rounded-md text-sm font-medium hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? "Adding..." : "Add User"}
                    </button>
                </form>

                {error && <div className="text-red-500 text-sm mb-4">{error}</div>}

                {/* Users List */}
                <div className="border rounded-xl overflow-hidden">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50 border-b">
                            <tr>
                                <th className="px-4 py-3 font-medium text-slate-700">Username</th>
                                <th className="px-4 py-3 font-medium text-slate-700 w-24 text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y">
                            {users.map((u) => (
                                <tr key={u} className="bg-white hover:bg-slate-50">
                                    <td className="px-4 py-3 font-medium">{u}</td>
                                    <td className="px-4 py-3 text-center">
                                        <button
                                            onClick={() => removeUser(u)}
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
                                    <td colSpan={2} className="px-4 py-8 text-center text-slate-500">
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
