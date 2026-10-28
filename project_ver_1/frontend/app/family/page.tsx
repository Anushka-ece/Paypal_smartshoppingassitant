"use client";

import { useEffect, useState } from "react";
import { useSession } from "../hooks/use-session";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Member = { id: number; email: string; role: string; is_verified: boolean };

export default function FamilyPage() {
  const { session, ready } = useSession();
  const [email, setEmail] = useState("");
  const [notice, setNotice] = useState("Loading session…");
  const [members, setMembers] = useState<Member[]>([]);

  async function load() {
    if (!session?.token) { setNotice("Sign in from the overview first."); return; }
    try {
      const response = await fetch(`${apiBase}/family/members`, { headers: { Authorization: `Bearer ${session.token}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to load family members.");
      setMembers(data); setNotice(`Loaded ${data.length} family member(s).`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to connect to the API."); }
  }
  useEffect(() => { if (ready) load(); }, [ready, session?.token]);

  async function inviteParent() {
    if (!session?.token || session.role !== "parent") { setNotice("Sign in as a parent first."); return; }
    try {
      const response = await fetch(`${apiBase}/family/invitations`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.token}` }, body: JSON.stringify({ email, role: "parent" }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to create invitation.");
      setNotice(data.invitation_token ? `Development invite token (deliver securely out of band): ${data.invitation_token}` : "Invitation created. Email delivery must be configured by the service operator.");
      setEmail(""); await load();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to connect to the API."); }
  }

  return <main style={{ maxWidth: 760, margin: "50px auto", padding: 24 }}>
    <p style={{ color: "#75817b", fontSize: 12, letterSpacing: 1 }}>FAMILY SETTINGS</p><h1 style={{ fontFamily: "Manrope, sans-serif" }}>Family members</h1>
    <p style={{ color: "#75817b", lineHeight: 1.6 }}>Co-parent invites require a verified parent. Child accounts stay disabled until a reviewed verifiable parental-consent flow is integrated.</p>
    {session?.role === "parent" && <section style={{ display: "flex", gap: 8, marginBottom: 20 }}><input aria-label="Co-parent email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Co-parent email" style={{ flex: 1, padding: 11, border: "1px solid #e7ece8", borderRadius: 9 }} /><button onClick={inviteParent} style={{ background: "#006b52", color: "white", border: 0, borderRadius: 10, padding: "11px 16px", fontWeight: 700 }}>Invite co-parent</button></section>}
    <section style={{ background: "white", border: "1px solid #e7ece8", borderRadius: 16, padding: 18 }}>{members.map((member) => <div key={member.id} style={{ padding: 12, borderBottom: "1px solid #eef1ee" }}><strong>{member.email}</strong><span style={{ float: "right" }}>{member.role} · {member.is_verified ? "verified" : "pending verification"}</span></div>)}</section>
    <p role="status" style={{ color: "#75817b", fontSize: 13, overflowWrap: "anywhere" }}>{notice}</p>
  </main>;
}
