"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "../hooks/use-session";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: number;
  family_id: number;
}

export default function LoginPage() {
  const router = useRouter();
  const { save } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        const detail =
          typeof data === "object" &&
          data !== null &&
          "detail" in data &&
          typeof data.detail === "string"
            ? data.detail
            : "Unable to sign in.";
        throw new Error(detail);
      }
      if (
        typeof data !== "object" ||
        data === null ||
        !("access_token" in data) ||
        typeof data.access_token !== "string" ||
        !("role" in data) ||
        typeof data.role !== "string"
      ) {
        throw new Error("The sign-in service returned an invalid session.");
      }

      const loginResult = data as LoginResponse;
      save({
        token: loginResult.access_token,
        role: loginResult.role,
        family_id: loginResult.family_id,
      });
      router.replace("/transactions");
    } catch (loginError) {
      setError(
        loginError instanceof Error
          ? loginError.message
          : "Unable to connect to the sign-in service.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 520, margin: "50px auto", padding: 24 }}>
      <p style={{ color: "#75817b", fontSize: 12, letterSpacing: 1 }}>FAMILY ACCOUNT</p>
      <h1 style={{ color: "#003087", fontFamily: "Manrope, sans-serif", marginBottom: 8 }}>
        Sign in to PennyPilot
      </h1>
      <p style={{ color: "#64748b", lineHeight: 1.6 }}>
        Sign in to view your family’s recorded transactions and PayPal refund statuses.
      </p>
      <form
        onSubmit={login}
        style={{
          display: "grid",
          gap: 14,
          background: "white",
          border: "1px solid #e2e8f0",
          borderRadius: 14,
          padding: 22,
        }}
      >
        <label style={{ display: "grid", gap: 6, color: "#475569", fontSize: 14 }}>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            style={{ border: "1px solid #cbd5e1", borderRadius: 8, padding: "0.7rem 0.8rem" }}
          />
        </label>
        <label style={{ display: "grid", gap: 6, color: "#475569", fontSize: 14 }}>
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            style={{ border: "1px solid #cbd5e1", borderRadius: 8, padding: "0.7rem 0.8rem" }}
          />
        </label>
        {error && (
          <div role="alert" style={{ background: "#fef2f2", color: "#991b1b", padding: "0.75rem", borderRadius: 8 }}>
            {error}
          </div>
        )}
        <button type="submit" className="button primary" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p style={{ color: "#64748b", fontSize: 14, marginTop: 16 }}>
        New here? <a href="/register" style={{ color: "#006b52", fontWeight: 700 }}>Create an account</a>
      </p>
    </main>
  );
}
