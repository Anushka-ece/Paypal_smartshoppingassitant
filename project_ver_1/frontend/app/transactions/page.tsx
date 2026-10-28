"use client";

import { useEffect, useState } from "react";
import { useSession } from "../hooks/use-session";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Item = { id: number; merchant_name: string; amount: string; currency: string; category?: string; status: string; is_flagged: boolean };

export default function TransactionsPage() {
  const { session, ready } = useSession();
  const token = session?.token ?? "";
  const [notice, setNotice] = useState("Loading session…");
  const [items, setItems] = useState<Item[]>([]);

  async function loadTransactions() {
    if (!token) { setNotice("Sign in from the overview first."); return; }
    try {
      const response = await fetch(`${apiBase}/transactions/`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to load transactions.");
      setItems(data);
      setNotice(`Loaded ${data.length} transaction(s).`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to reach the API."); }
  }
  useEffect(() => { if (ready) loadTransactions(); }, [ready, token]);

  async function decide(id: number, action: "approve" | "review" | "freeze_allowance") {
    try {
      const response = await fetch(`${apiBase}/transactions/${id}/decision`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ action }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to save decision.");
      setNotice(data.message);
      await loadTransactions();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to reach the API."); }
  }

  return <main style={{ maxWidth: 900, margin: "50px auto", padding: 24 }}>
    <p style={{ color: "#75817b", fontSize: 12, letterSpacing: 1 }}>FAMILY ACTIVITY</p><h1 style={{ fontFamily: "Manrope, sans-serif" }}>Transactions</h1>
    <p style={{ color: "#75817b", lineHeight: 1.6 }}>PayPal transactions are observed after processing. Decisions here affect internal review and future allowances only; they cannot cancel or dispute a captured PayPal payment.</p>
    <section style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "18px 0" }}><button onClick={loadTransactions} className="button">Refresh</button></section>
    <section style={{ background: "white", border: "1px solid #e7ece8", borderRadius: 16, padding: 20 }}>
      {items.length ? items.map((item) => <div key={item.id} style={{ padding: "13px 0", borderBottom: "1px solid #eef1ee", display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}><span><strong>{item.merchant_name}</strong><br /><small>{item.category ?? "Uncategorized"} · {item.status}{item.is_flagged ? " · Flagged" : ""}</small></span><strong>${Number(item.amount).toFixed(2)} {item.currency}</strong>{session?.role === "parent" && item.is_flagged && <span style={{ display: "flex", gap: 6 }}><button className="button small" onClick={() => decide(item.id, "approve")}>Approve internally</button><button className="button small" onClick={() => decide(item.id, "review")}>Review</button></span>}</div>) : <p style={{ color: "#75817b" }}>No transactions loaded.</p>}
    </section>
    {session?.role === "parent" && <section style={{ marginTop: 16 }}><button className="button" onClick={() => items[0] && decide(items[0].id, "freeze_allowance")}>Freeze future allowance schedules</button></section>}
    <p role="status" style={{ color: "#75817b", fontSize: 13 }}>{notice}</p>
  </main>;
}
