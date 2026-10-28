"use client";

import { useEffect, useState } from "react";
import { useSession } from "../hooks/use-session";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Budget = { id: number; category_name: string; allocated_amount: string; spent_amount: string; currency: string };

export default function BudgetsPage() {
  const { session, ready } = useSession();
  const [category, setCategory] = useState("Free spend");
  const [amount, setAmount] = useState("50.00");
  const [notice, setNotice] = useState("Loading session…");
  const [budgets, setBudgets] = useState<Budget[]>([]);

  async function load() {
    if (!session?.token) { setNotice("Sign in from the overview first."); return; }
    try {
      const response = await fetch(`${apiBase}/allowances/`, { headers: { Authorization: `Bearer ${session.token}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to load budgets.");
      setBudgets(data);
      setNotice(`Loaded ${data.length} budget envelope(s).`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to reach the API."); }
  }
  useEffect(() => { if (ready) load(); }, [ready, session?.token]);

  async function saveBudget() {
    if (!session?.token || session.role !== "parent") { setNotice("A signed-in parent is required to manage budgets."); return; }
    try {
      const response = await fetch(`${apiBase}/allowances/budgets`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.token}` }, body: JSON.stringify({ category_name: category, allocated_amount: amount, currency: "USD" }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to save budget.");
      setNotice(`${data.category_name} budget saved: $${Number(data.allocated_amount).toFixed(2)} USD.`);
      await load();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to connect to the API."); }
  }

  return <main style={{ maxWidth: 760, margin: "50px auto", padding: 24 }}>
    <p style={{ color: "#75817b", fontSize: 12, letterSpacing: 1 }}>BUDGET PLANNING</p><h1 style={{ fontFamily: "Manrope, sans-serif" }}>Budget envelopes</h1>
    <p style={{ color: "#75817b", lineHeight: 1.6 }}>Version 1 budgets use USD only. Envelopes track spending; they do not restrict PayPal checkout or represent cash balances.</p>
    {session?.role === "parent" && <section style={{ display: "grid", gap: 12, background: "white", border: "1px solid #e7ece8", borderRadius: 16, padding: 22 }}>
      <label>Envelope category<input value={category} onChange={(event) => setCategory(event.target.value)} style={{ display: "block", width: "100%", marginTop: 6, padding: 11, border: "1px solid #e7ece8", borderRadius: 9 }} /></label>
      <label>Monthly allocation (USD)<input type="number" min="0" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} style={{ display: "block", width: "100%", marginTop: 6, padding: 11, border: "1px solid #e7ece8", borderRadius: 9 }} /></label>
      <button onClick={saveBudget} style={{ justifySelf: "start", background: "#006b52", color: "white", border: 0, borderRadius: 10, padding: "11px 16px", fontWeight: 700 }}>Save envelope</button>
    </section>}
    <section style={{ marginTop: 18, background: "white", border: "1px solid #e7ece8", borderRadius: 16, padding: 18 }}>{budgets.map((item) => { const allocated = Number(item.allocated_amount); const spent = Number(item.spent_amount); return <div key={item.id} style={{ padding: 12, borderBottom: "1px solid #eef1ee" }}><strong>{item.category_name}</strong><span style={{ float: "right" }}>${spent.toFixed(2)} / ${allocated.toFixed(2)} {item.currency}</span></div>; })}{!budgets.length && <p style={{ color: "#75817b" }}>No budget envelopes.</p>}</section>
    <p role="status" style={{ color: "#75817b", fontSize: 13 }}>{notice}</p>
  </main>;
}
