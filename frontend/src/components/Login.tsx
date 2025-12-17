
import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Lock } from "lucide-react";

interface LoginProps {
    onLogin: (username: string) => void;
}

export default function Login({ onLogin }: LoginProps) {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setLoading(true);
        setError("");

        try {
            const res = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
            });

            if (!res.ok) throw new Error("Authentication failed");

            const data = await res.json();
            onLogin(data.username);
        } catch (err) {
            setError("Invalid credentials. Please try again.");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
            <Card className="w-full max-w-md bg-white shadow-xl rounded-2xl">
                <CardHeader className="text-center pb-2">
                    <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-slate-200">
                        <Lock className="size-6 text-slate-700" />
                    </div>
                    <CardTitle className="text-2xl font-semibold">Sign in</CardTitle>
                    <p className="text-sm text-muted-foreground mt-2">
                        Use your Windows session credentials
                    </p>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70" htmlFor="username">
                                Username
                            </label>
                            <input
                                id="username"
                                type="text"
                                placeholder="domain\user"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70" htmlFor="password">
                                Password
                            </label>
                            <input
                                id="password"
                                type="password"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                required
                            />
                        </div>
                        {error && <div className="text-sm text-red-500 font-medium">{error}</div>}
                        <Button type="submit" className="w-full rounded-xl" disabled={loading}>
                            {loading ? "Verifying..." : "Sign in"}
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
}
