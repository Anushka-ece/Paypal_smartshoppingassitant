"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSession } from "./hooks/use-session";

type Transaction = { id: string; merchant: string; description: string; amount: number; icon: string; status: string; review?: boolean; createdAt?: string };
type Budget = { id: number; category_name: string; spent_amount: string | number; allocated_amount: string | number; currency: string };
const menu = [{ label: "Overview", icon: "▦" }, { label: "Transactions", icon: "↕" }, { label: "Budgets", icon: "◉" }, { label: "Family", icon: "♧" }, { label: "Spending rules", icon: "⌘" }];
const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Dashboard() {
  const [active, setActive] = useState("Overview");
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const { session, ready, save, clear } = useSession();
  const token = session?.token ?? "";
  const [notice, setNotice] = useState("Demo preview · Connect the backend and sign in to load your family's live data.");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showLogin, setShowLogin] = useState(false);
  const pending = useMemo(() => transactions.filter((item) => item.review).length, [transactions]);

  async function loadFamilyData(accessToken: string) {
    const txResponse = await fetch(`${apiBase}/transactions/`, { headers: { Authorization: `Bearer ${accessToken}` } });
    if (!txResponse.ok) throw new Error((await txResponse.json()).detail ?? "Signed in, but transaction data could not be loaded.");
    const live = await txResponse.json();
    setTransactions(live.map((tx: { id: number; merchant_name: string; amount: string | number; category?: string; status: string; is_flagged: boolean }) => ({
      id: String(tx.id), merchant: tx.merchant_name, description: `${tx.category ?? "Uncategorized"} · ${tx.status}`, amount: Number(tx.amount), icon: "💳", status: tx.is_flagged ? "Needs review" : "Approved", review: tx.is_flagged,
    })));
    const budgetResponse = await fetch(`${apiBase}/allowances/`, { headers: { Authorization: `Bearer ${accessToken}` } });
    if (budgetResponse.ok) setBudgets(await budgetResponse.json());
  }

  async function connectAccount() {
    try {
      const response = await fetch(`${apiBase}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to sign in.");
      save({ token: data.access_token, role: data.role });
      await loadFamilyData(data.access_token);
      setNotice("Signed in. Live family transaction data is connected.");
      setShowLogin(false);
    } catch (error) {
      setToken("");
      setTransactions([]);
      setBudgets([]);
      setNotice(error instanceof Error ? error.message : "Unable to connect to the API.");
    }
  }

  function resolveReview(id: string) {
    fetch(`${apiBase}/transactions/${id}/decision`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ action: "review" }) })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail ?? "Unable to save decision.");
        setNotice(data.message);
        await loadFamilyData(token);
      })
      .catch((error) => setNotice(error instanceof Error ? error.message : "Unable to save review."));
  }

  const totalSpent = budgets.reduce((sum, item) => sum + Number(item.spent_amount), 0);
  const totalAllocated = budgets.reduce((sum, item) => sum + Number(item.allocated_amount), 0);
  const remaining = Math.max(0, totalAllocated - totalSpent);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">P</span><span>penny<em>pilot</em></span></div>
        <div className="family-switch">YOUR FAMILY<strong>🌿 &nbsp;Your family⌄</strong></div>
        <div className="nav-label">WORKSPACE</div>
            <nav className="nav-list" aria-label="Main navigation">{menu.map((item) => {
            const href = item.label === "Overview" ? "/" : item.label === "Transactions" ? "/transactions" : item.label === "Budgets" ? "/budgets" : item.label === "Family" ? "/family" : "/policies";
          return <Link key={item.label} href={href} className={`nav-item ${active === item.label ? "active" : ""}`}><span className="nav-icon">{item.icon}</span>{item.label}{item.label === "Transactions" && pending > 0 && <span className="pill review">{pending}</span>}</Link>;
        })}</nav>
        <div className="sidebar-bottom"><div className="profile"><span className="avatar">PP</span><span><strong>Family account</strong><small>{session?.role ?? "Signed out"}</small></span></div></div>
      </aside>
      <main className="main">
        <header className="topbar"><div><p className="eyebrow">FAMILY FINANCES</p><h1>{active === "Overview" ? token ? "Your family overview" : "Welcome to PennyPilot" : active}</h1></div><div className="top-actions"><button className="icon-btn" aria-label="Notifications">♧ {pending > 0 && <span className="pill review">{pending}</span>}</button>{token && <Link className="button primary" href="/connect">PayPal settings</Link>}<button className="button" onClick={() => token ? (clear(), setTransactions([]), setBudgets([]), setNotice("Signed out.")) : setShowLogin((value) => !value)}>{token ? "Sign out" : "Sign in"}</button><button className="icon-btn mobile-menu" onClick={() => setActive("Overview")}>☰</button></div></header>
        {notice && <div className="notice" role="status">{notice}</div>}
        {showLogin && <section className="card" style={{ marginBottom: 18 }}><div className="card-head"><div><h2>Sign in to your family account</h2><p>Connect to the PennyPilot API. PayPal linking is managed separately through OAuth.</p></div><button className="icon-btn" onClick={() => setShowLogin(false)}>×</button></div><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><input aria-label="Email" placeholder="Parent email" value={email} onChange={(event) => setEmail(event.target.value)} /><input aria-label="Password" type="password" placeholder="Password" value={password} onChange={(event) => setPassword(event.target.value)} /><button className="button primary" onClick={connectAccount}>Sign in</button></div></section>}
        {!token && !showLogin && <section className="card"><div className="card-head"><div><h2>Start with your family account</h2><p>Create an account, complete parent verification, then connect a PayPal Sandbox account to explore the workflow.</p></div></div><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><Link className="button primary" href="/register">Create parent account</Link><button className="button" onClick={() => setShowLogin(true)}>I already have an account</button></div><p className="footer-note">Dashboard values and activity are hidden until authenticated data is loaded.</p></section>}
        {token && <section className="grid stats">
          <article className="card"><div className="stat-label">Budget allocation <span className="stat-icon">＄</span></div><div className="stat-value">${totalAllocated.toFixed(2)}</div><div className="trend">Across {budgets.length} envelopes · USD</div></article>
          <article className="card"><div className="stat-label">Tracked spend <span className="stat-icon">↘</span></div><div className="stat-value">${totalSpent.toFixed(2)}</div><div className="trend">Current envelope totals</div></article>
          <article className="card"><div className="stat-label">Envelope remaining <span className="stat-icon">◉</span></div><div className="stat-value">${remaining.toFixed(2)}</div><div className="trend">Not a PayPal available balance</div></article>
          <article className="card"><div className="stat-label">Needs your attention <span className="stat-icon">♧</span></div><div className="stat-value">{pending}</div><div className="trend" style={{ color: pending ? "#a86215" : undefined }}>Spending rule alerts</div></article>
        </section>}
        {token && <section className="grid content-grid">
          <article className="card"><div className="card-head"><div><h2>Budget envelopes</h2><p>Tracked amounts vs. allocations · USD</p></div><Link className="button soft small" href="/budgets">Manage budgets ↗</Link></div><div className="budget-list">{budgets.length ? budgets.map((budget) => { const spent = Number(budget.spent_amount); const limit = Number(budget.allocated_amount); return <div className="budget-row" key={budget.id}><div className="budget-info"><strong>{budget.category_name}</strong><span>${spent.toFixed(2)} <span style={{ color: "#a5ada8" }}>/ ${limit.toFixed(2)}</span></span></div><div className="bar"><div className={`bar-fill ${limit && spent / limit >= 0.8 ? "warn" : ""} ${limit && spent / limit >= 1 ? "high" : ""}`} style={{ width: `${limit ? Math.min(100, spent / limit * 100) : 0}%` }} /></div></div>; }) : <div className="empty">No budget envelopes have been created.</div>}</div></article>
          <article className="card"><div className="card-head"><div><h2>Envelope summary</h2><p>Family budgeting ledger · USD</p></div><span className="pill">Tracking</span></div><div className="spending-ring"><div className="ring-inner"><strong>${totalSpent.toFixed(0)}</strong><span>of ${totalAllocated.toFixed(0)} allocated</span></div></div><div className="ring-caption">${remaining.toFixed(2)} budget allocation remaining; this is not account cash.</div></article>
        </section>}
        {token && <section className="grid content-grid">
          <article className="card"><div className="card-head"><div><h2>Recent activity</h2><p>Latest family transactions</p></div><button className="button small" onClick={() => setActive("Transactions")}>All transactions ↗</button></div><div className="transaction-list">{transactions.length ? transactions.slice(0, 5).map((transaction) => <div className="transaction" key={transaction.id}><span className="merchant-icon">{transaction.icon}</span><span><strong>{transaction.merchant}</strong><small>{transaction.description}</small></span><span className="amount">−${transaction.amount.toFixed(2)}<small><span className={`pill ${transaction.review ? "review" : ""}`}>{transaction.status}</span></small></span></div>) : <div className="empty">No transactions have synced yet.</div>}</div></article>
          <article className="card"><div className="card-head"><div><h2>Parent review</h2><p>Transactions flagged by family rules</p></div><span className="pill review">{pending} pending</span></div>{transactions.filter((transaction) => transaction.review).length ? transactions.filter((transaction) => transaction.review).map((transaction) => <div className="approval" key={transaction.id}><span className="approval-icon">⚑</span><span className="approval-main"><strong>{transaction.merchant}</strong><small>${transaction.amount.toFixed(2)} · Check your spending rules</small></span><span className="approval-actions"><button className="button soft small" onClick={() => resolveReview(transaction.id)}>Review</button></span></div>) : <div className="empty">You're all caught up. New alerts will appear here.</div>}<p className="footer-note">Review is a UI action in this preview; transaction approvals are not sent to PayPal.</p></article>
        </section>}
        <div className="footer-note">Budgets are internal tracking envelopes. This app cannot block or reverse an external PayPal checkout.</div>
      </main>
    </div>
  );
}
