"use client";

import { useEffect, useState } from "react";
import { useSession } from "../hooks/use-session";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Rule = { id: number; rule_text: string; created_at: string };

export default function PoliciesPage() {
  const { session, ready } = useSession();
  const [rule, setRule] = useState("");
  const [notice, setNotice] = useState("Loading session…");
  const [rules, setRules] = useState<Rule[]>([]);

  async function load() {
    if (!session?.token) { setNotice("Sign in from the overview first."); return; }
    try {
      const response = await fetch(`${apiBase}/guardrails/rules`, { headers: { Authorization: `Bearer ${session.token}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to load rules.");
      setRules(data);
      setNotice(`Loaded ${data.length} active rule(s).`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to reach the API."); }
  }
  useEffect(() => { if (ready) load(); }, [ready, session?.token]);

  async function addRule() {
    if (!session?.token || session.role !== "parent") { setNotice("Sign in as a parent before adding a spending policy."); return; }
    try {
      const response = await fetch(`${apiBase}/guardrails/rules`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.token}` }, body: JSON.stringify({ rule_text: rule }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to save this rule.");
      setNotice("Rule saved for this family."); setRule(""); await load();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to connect to the API."); }
  }

  return <main style={{ maxWidth: 760, margin: "50px auto", padding: 24 }}>
    <p style={{ color: "#75817b", fontSize: 12, letterSpacing: 1 }}>FAMILY SAFETY</p><h1 style={{ fontFamily: "Manrope, sans-serif" }}>Spending rules</h1>
    <p style={{ color: "#75817b", lineHeight: 1.6 }}>Rules flag transactions after a PayPal event; they do not prevent an off-site checkout.</p>
    {session?.role === "parent" && <section style={{ background: "white", border: "1px solid #e7ece8", borderRadius: 16, padding: 22 }}><label htmlFor="rule">Your rule</label><textarea id="rule" value={rule} onChange={(event) => setRule(event.target.value)} placeholder="Flag any video game purchase over $25" rows={4} style={{ display: "block", width: "100%", margin: "12px 0", padding: 12, border: "1px solid #e7ece8", borderRadius: 10, resize: "vertical" }} /><button onClick={addRule} style={{ background: "#006b52", color: "white", border: 0, borderRadius: 10, padding: "11px 16px", fontWeight: 700 }}>Save rule</button></section>}
    <section style={{ marginTop: 16, background: "white", border: "1px solid #e7ece8", borderRadius: 16, padding: 18 }}>{rules.map((item) => <div key={item.id} style={{ padding: 12, borderBottom: "1px solid #eef1ee" }}>{item.rule_text}</div>)}{!rules.length && <p style={{ color: "#75817b" }}>No active rules.</p>}</section>
    <p role="status" style={{ color: "#75817b", fontSize: 13 }}>{notice}</p>
  </main>;
}
