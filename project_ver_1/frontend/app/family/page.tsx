"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useSession } from "../hooks/use-session";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

interface Member {
  id: number;
  name: string;
  email: string;
  role: "PARENT" | "CO_PARENT" | "CHILD";
  is_verified: boolean;
  coppa_consent_status: string;
}

interface Invitation {
  token: string;
  email: string;
  expires_at: string;
}

export default function FamilyPage() {
  const { session, ready } = useSession();
  const [members, setMembers] = useState<Member[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"co_parent" | "child">("child");
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadMembers = useCallback(async () => {
    if (!session?.token || !session.family_id) {
      setError("Sign in to view your family members.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${apiBase}/api/family/members?family_id=${session.family_id}`,
        {
          headers: { Authorization: `Bearer ${session.token}` },
          cache: "no-store",
        },
      );
      const data: unknown = await response.json();
      if (!response.ok) {
        const detail =
          typeof data === "object" &&
          data !== null &&
          "detail" in data &&
          typeof data.detail === "string"
            ? data.detail
            : "Unable to load family members.";
        throw new Error(detail);
      }
      if (!Array.isArray(data)) {
        throw new Error("The family service returned an invalid response.");
      }
      setMembers(data as Member[]);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load family members.");
    } finally {
      setLoading(false);
    }
  }, [session?.family_id, session?.token]);

  useEffect(() => {
    if (ready && session?.token) void loadMembers();
    else if (ready) setError("Sign in to view your family members.");
  }, [ready, session?.token, loadMembers]);

  async function createInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session?.token || !session.family_id) {
      setError("Sign in to invite a family member.");
      return;
    }

    setError(null);
    setNotice(null);
    setInvitation(null);
    try {
      const response = await fetch(`${apiBase}/api/family/invitations`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.token}`,
        },
        body: JSON.stringify({
          email: inviteEmail,
          role: inviteRole,
          family_id: session.family_id,
        }),
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        const detail =
          typeof data === "object" &&
          data !== null &&
          "detail" in data &&
          typeof data.detail === "string"
            ? data.detail
            : "Unable to create the family invitation.";
        throw new Error(detail);
      }
      setInvitation(data as Invitation);
      setInviteEmail("");
      setNotice("Invitation token created. Share it securely with the invited member.");
    } catch (inviteError) {
      setError(inviteError instanceof Error ? inviteError.message : "Unable to create the invitation.");
    }
  }

  const isParent = session?.role.toUpperCase() === "PARENT" || session?.role.toUpperCase() === "CO_PARENT";

  return (
    <main>
      <h1 style={{ fontSize: "1.8rem", margin: "0 0 0.4rem", color: "#003087" }}>Family members</h1>
      <p style={{ color: "#64748b", lineHeight: 1.6 }}>
        View members in your family account and create time-limited invitation tokens.
        Invite acceptance and parental-consent verification are not implemented in this demo.
      </p>

      {!session?.token && ready && <p role="alert">Sign in to view family information. <a href="/login">Go to login</a>.</p>}
      {error && <div role="alert" style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", padding: "0.8rem 1rem", borderRadius: 10, margin: "1rem 0" }}>{error}</div>}
      {notice && <p role="status" style={{ color: "#047857" }}>{notice}</p>}

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1.5rem", marginTop: "1.5rem" }}>
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <h2 style={{ fontSize: "1.2rem", color: "#003087" }}>Family members</h2>
            <button type="button" className="button" onClick={() => void loadMembers()} disabled={loading}>
              {loading ? "Refreshing…" : "Refresh"}
            </button>
          </div>
          {members.length === 0 && !loading && <p style={{ color: "#64748b" }}>No family members found.</p>}
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {members.map((member) => (
              <article key={member.id} style={{ background: "white", padding: "1rem", borderRadius: 10, border: "1px solid #e2e8f0" }}>
                <strong>{member.name}</strong>
                <div style={{ color: "#64748b", fontSize: 14 }}>{member.email}</div>
                <div style={{ marginTop: 6, color: "#475569", fontSize: 13 }}>
                  {member.role.replace("_", " ")} · {member.is_verified ? "Verified" : "Unverified"}
                </div>
              </article>
            ))}
          </div>
        </div>

        {session?.token && isParent && (
          <section style={{ background: "white", padding: "1.25rem", borderRadius: 12, border: "1px solid #e2e8f0", alignSelf: "start" }}>
            <h2 style={{ fontSize: "1.2rem", color: "#003087", marginTop: 0 }}>Invite a family member</h2>
            <form onSubmit={createInvitation} style={{ display: "grid", gap: 12 }}>
              <label style={{ display: "grid", gap: 6, color: "#475569", fontSize: 14 }}>
                Email address
                <input type="email" required value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} placeholder="family@example.com" style={{ padding: 10, border: "1px solid #cbd5e1", borderRadius: 8 }} />
              </label>
              <label style={{ display: "grid", gap: 6, color: "#475569", fontSize: 14 }}>
                Role
                <select value={inviteRole} onChange={(event) => setInviteRole(event.target.value as "co_parent" | "child")} style={{ padding: 10, border: "1px solid #cbd5e1", borderRadius: 8, background: "white" }}>
                  <option value="child">Child</option>
                  <option value="co_parent">Co-parent</option>
                </select>
              </label>
              <button type="submit" className="button">Create invitation token</button>
            </form>
            {invitation && (
              <div style={{ marginTop: 16, padding: 12, background: "#f8fafc", borderRadius: 8, overflowWrap: "anywhere" }}>
                <div>Token for {invitation.email}</div>
                <code>{invitation.token}</code>
                <div style={{ color: "#64748b", fontSize: 13 }}>Expires {new Date(invitation.expires_at).toLocaleString()}</div>
              </div>
            )}
          </section>
        )}
      </section>
    </main>
  );
}
