"use client";

import { useState } from "react";
import { useSession } from "../hooks/use-session";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function ConnectPayPalPage() {
  const { session, ready } = useSession();
  const [notice, setNotice] = useState("Link PayPal using the backend's OAuth consent flow.");
  const [busy, setBusy] = useState(false);

  async function beginLink() {
    if (!session?.token) {
      setNotice("Sign in before linking a PayPal account.");
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`${apiBase}/auth/paypal/authorize`, {
        headers: { Authorization: `Bearer ${session.token}` },
        cache: "no-store",
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to start PayPal linking.");
      window.location.assign(data.auth_url);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to connect to the API.");
      setBusy(false);
    }
  }

  return <main style={{ maxWidth: 680, margin: "70px auto", padding: 24 }}>
    <p style={{ color: "#75817b", fontSize: 12, letterSpacing: 1 }}>CONNECTED ACCOUNTS</p>
    <h1 style={{ fontFamily: "Manrope, sans-serif" }}>Link PayPal</h1>
    <p style={{ color: "#75817b", lineHeight: 1.65 }}>You'll be redirected to PayPal for OpenID account identity consent. This verifies account identity only; it does not automatically grant access to personal purchases. Transaction Search is an app-level reporting API and may require separate business permissions and approval.</p>
    <button onClick={beginLink} disabled={busy || !ready || !session?.token} style={{ background: "#006b52", color: "#fff", border: 0, borderRadius: 10, padding: "12px 16px", fontWeight: 700 }}>{busy ? "Redirecting…" : "Continue to PayPal"}</button>
    <p role="status" style={{ color: "#75817b", fontSize: 13 }}>{notice}</p>
  </main>;
}
