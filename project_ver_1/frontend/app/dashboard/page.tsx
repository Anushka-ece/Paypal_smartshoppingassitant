"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "../hooks/use-session";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

interface TransactionItem {
  id: number;
  merchant_name: string | null;
  clean_merchant_name: string | null;
  amount: number;
  currency: string;
  category: string | null;
  status: string;
  is_flagged: boolean;
  flagged_reason: string | null;
  created_at: string | null;
}

export default function DashboardPage() {
  const { session, ready } = useSession();
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTransactions = useCallback(async () => {
    if (!session?.token || !session.family_id) {
      setError("Sign in to view your family's financial activity.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${apiBase}/api/transactions?family_id=${session.family_id}&limit=50`,
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
            : "Unable to load family transactions.";
        throw new Error(detail);
      }
      if (!Array.isArray(data)) {
        throw new Error("The transaction service returned an invalid response.");
      }
      setTransactions(data as TransactionItem[]);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to connect to the transaction service.",
      );
    } finally {
      setLoading(false);
    }
  }, [session?.family_id, session?.token]);

  useEffect(() => {
    if (ready && session?.token) void loadTransactions();
    else if (ready) setError("Sign in to view your family's financial activity.");
  }, [ready, session?.token, loadTransactions]);

  const summary = useMemo(
    () => ({
      total: transactions.reduce((sum, item) => sum + item.amount, 0),
      completed: transactions.filter((item) => item.status === "COMPLETED").length,
      refunds: transactions.filter(
        (item) => item.status === "REFUNDED" || item.status === "PARTIALLY_REFUNDED",
      ).length,
      flagged: transactions.filter((item) => item.is_flagged).length,
    }),
    [transactions],
  );

  return (
    <main>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: "1.5rem" }}>
        <div>
          <h1 style={{ fontSize: "1.8rem", margin: "0 0 0.4rem", color: "#003087" }}>Family financial overview</h1>
          <p style={{ margin: 0, color: "#64748b" }}>A live summary of expenses and transaction statuses recorded for your family.</p>
        </div>
        <a href="/transactions" className="button">Record an expense</a>
      </div>

      {!session?.token && ready && (
        <div role="alert" style={{ background: "#fff7e8", color: "#82551c", padding: "0.8rem 1rem", borderRadius: "0.5rem", marginBottom: "1.5rem" }}>
          <a href="/login" style={{ color: "#82551c", fontWeight: 700 }}>Sign in</a> to see your family's live financial summary.
        </div>
      )}
      {error && session?.token && (
        <div role="alert" style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", padding: "0.8rem 1rem", borderRadius: "0.5rem", marginBottom: "1.5rem" }}>
          {error}
        </div>
      )}

      <section aria-label="Family financial summary" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
        {[
          { label: "RECORDED EXPENSES", value: new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(summary.total), color: "#003087" },
          { label: "TRANSACTIONS", value: transactions.length, color: "#0284c7" },
          { label: "REFUNDED / PARTIAL", value: summary.refunds, color: "#b45309" },
          { label: "FLAGGED FOR REVIEW", value: summary.flagged, color: "#b91c1c" },
        ].map((stat) => (
          <div key={stat.label} style={{ background: "white", padding: "1.25rem", borderRadius: "0.5rem", border: "1px solid #e2e8f0" }}>
            <div style={{ color: "#64748b", fontSize: "0.85rem", fontWeight: 600 }}>{stat.label}</div>
            <div style={{ fontSize: "1.75rem", fontWeight: 800, color: stat.color, marginTop: "0.25rem" }}>{stat.value}</div>
          </div>
        ))}
      </section>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: "1rem" }}>
        <h2 style={{ fontSize: "1.3rem", color: "#003087", margin: 0 }}>Recent family activity</h2>
        <button type="button" className="button" onClick={() => void loadTransactions()} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <section style={{ background: "white", borderRadius: "0.5rem", border: "1px solid #e2e8f0", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.95rem" }}>
          <thead>
            <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0", color: "#64748b" }}>
              <th style={{ padding: "0.75rem 1rem" }}>Merchant</th>
              <th style={{ padding: "0.75rem 1rem" }}>Category</th>
              <th style={{ padding: "0.75rem 1rem" }}>Amount</th>
              <th style={{ padding: "0.75rem 1rem" }}>Status</th>
              <th style={{ padding: "0.75rem 1rem" }}>Date</th>
            </tr>
          </thead>
          <tbody>
            {!loading && transactions.length === 0 && (
              <tr><td colSpan={5} style={{ padding: "1rem", color: "#64748b" }}>No expenses recorded yet. <a href="/transactions">Add your first expense</a>.</td></tr>
            )}
            {transactions.map((transaction) => (
              <tr key={transaction.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                <td style={{ padding: "0.75rem 1rem", fontWeight: 600 }}>{transaction.clean_merchant_name || transaction.merchant_name || "Expense"}</td>
                <td style={{ padding: "0.75rem 1rem" }}>{transaction.category || "Uncategorized"}</td>
                <td style={{ padding: "0.75rem 1rem", fontWeight: 700 }}>{new Intl.NumberFormat(undefined, { style: "currency", currency: transaction.currency }).format(transaction.amount)}</td>
                <td style={{ padding: "0.75rem 1rem" }}>{transaction.is_flagged ? "FLAGGED" : transaction.status}</td>
                <td style={{ padding: "0.75rem 1rem", color: "#64748b" }}>{transaction.created_at ? new Date(transaction.created_at).toLocaleDateString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <p style={{ color: "#64748b", fontSize: 13, marginTop: "1rem" }}>
        {summary.completed} completed transaction{summary.completed === 1 ? "" : "s"} recorded. The dashboard reflects backend data; it does not display a live PayPal balance.
      </p>
    </main>
  );
}
