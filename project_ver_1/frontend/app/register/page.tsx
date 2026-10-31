"use client";

import { useState } from "react";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function RegisterPage() {
  const [familyName, setFamilyName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState("");

  async function register() {
    try {
      const response = await fetch(`${apiBase}/auth/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ family_name: familyName, email, password }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to create account.");
      setNotice("Parent account created. Parent verification and consent workflow must be completed before family money features are enabled.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to connect to the API."); }
  }

  return <main style={{ maxWidth: 620, margin: "65px auto", padding: 24 }}>
    <p style={{ color: "#75817b", fontSize: 12, letterSpacing: 1 }}>GET STARTED</p><h1 style={{ fontFamily: "Manrope, sans-serif" }}>Create your family account</h1>
    <p style={{ color: "#75817b", lineHeight: 1.6 }}>Initial parent accounts remain unverified. Financial actions and child profiles are disabled until the real verification/parental-consent process is integrated.</p>
    <section style={{ display: "grid", gap: 12, background: "white", border: "1px solid #e7ece8", borderRadius: 16, padding: 22 }}>
      <input value={familyName} onChange={(event) => setFamilyName(event.target.value)} placeholder="Family name" style={{ padding: 12, border: "1px solid #e7ece8", borderRadius: 9 }} />
      <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" placeholder="Parent email" style={{ padding: 12, border: "1px solid #e7ece8", borderRadius: 9 }} />
      <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="Password (12+ characters)" style={{ padding: 12, border: "1px solid #e7ece8", borderRadius: 9 }} />
      <button onClick={register} style={{ justifySelf: "start", background: "#006b52", color: "white", border: 0, borderRadius: 10, padding: "12px 16px", fontWeight: 700 }}>Create account</button>
    </section>
    <p role="status" style={{ color: "#75817b", fontSize: 13 }}>{notice}</p>
  </main>;
}
