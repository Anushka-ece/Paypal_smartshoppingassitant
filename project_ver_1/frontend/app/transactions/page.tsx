"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "../hooks/use-session";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Item = {
  id: number;
  merchant_name: string | null;
  clean_merchant_name: string | null;
  amount: number;
  currency: string;
  category: string | null;
  status: string;
  refund_id: string | null;
  is_flagged: boolean;
  flagged_reason: string | null;
  created_at: string | null;
  updated_at: string | null;
};

const refundStatuses = new Set(["REFUNDED", "PARTIALLY_REFUNDED"]);

export default function TransactionsPage() {
  const { session, ready } = useSession();
  const [familyIdInput, setFamilyIdInput] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session?.family_id) setFamilyIdInput(String(session.family_id));
  }, [session?.family_id]);

  const familyId = session?.family_id ?? Number(familyIdInput);
  const validFamilyId = Number.isInteger(familyId) && familyId > 0;

  const loadTransactions = useCallback(async () => {
    if (!session?.token) {
      setError("Sign in to view family transactions.");
      return;
    }
    if (!validFamilyId) {
      setError("Enter a valid family ID to load its transactions.");
      return;
    }

    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(
        `${apiBase}/api/transactions?family_id=${encodeURIComponent(String(familyId))}&limit=200`,
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
            : "Unable to load transactions.";
        throw new Error(detail);
      }
      if (!Array.isArray(data)) {
        throw new Error("The transaction service returned an invalid response.");
      }
      setItems(data);
      setNotice(`Updated ${data.length} transaction${data.length === 1 ? "" : "s"}.`);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to connect to the transaction service.",
      );
    } finally {
      setLoading(false);
    }
  }, [familyId, session?.token, validFamilyId]);

  useEffect(() => {
    if (ready && session?.token && validFamilyId) void loadTransactions();
    else if (ready && !session?.token) setError("Sign in to view family transactions.");
  }, [ready, session?.token, validFamilyId, loadTransactions]);

  const counts = useMemo(
    () => ({
      total: items.length,
      completed: items.filter((item) => item.status === "COMPLETED").length,
      refunded: items.filter((item) => refundStatuses.has(item.status)).length,
      flagged: items.filter((item) => item.is_flagged).length,
    }),
    [items],
  );

  const filteredItems =
    statusFilter === "REFUNDS"
      ? items.filter((item) => refundStatuses.has(item.status))
      : statusFilter === "ALL"
        ? items
        : items.filter((item) => item.status === statusFilter);

  return (
    <main style={{ maxWidth: 1000, margin: "40px auto", padding: 24 }}>
      <p style={{ color: "#75817b", fontSize: 12, letterSpacing: 1 }}>FAMILY ACTIVITY</p>
      <h1 style={{ fontFamily: "Manrope, sans-serif", color: "#003087", margin: "0 0 0.5rem" }}>
        Transactions &amp; Refunds
      </h1>
      <p style={{ color: "#64748b", lineHeight: 1.6, maxWidth: 760 }}>
        Live statuses come from transactions recorded by the backend. Refunds appear after
        PayPal sends a verified refund webhook; this page never estimates or invents a refund
        amount. A transaction review here does not cancel or dispute a PayPal payment.
      </p>

      {!session?.token && ready && (
        <div role="alert" style={{ background: "#fff7e8", color: "#82551c", padding: "0.8rem 1rem", borderRadius: 10, margin: "1rem 0" }}>
          <a href="/login" style={{ color: "#82551c", fontWeight: 700 }}>Sign in</a> to view family transaction statuses.
        </div>
      )}

      {session?.token && !session.family_id && (
        <section style={{ display: "flex", flexWrap: "wrap", alignItems: "end", gap: 10, background: "white", border: "1px solid #e2e8f0", borderRadius: 12, padding: 16, margin: "1rem 0" }}>
          <label htmlFor="family-id" style={{ display: "grid", gap: 6, color: "#64748b", fontSize: 14 }}>
            Family ID
            <input
              id="family-id"
              inputMode="numeric"
              value={familyIdInput}
              onChange={(event) => setFamilyIdInput(event.target.value)}
              placeholder="Enter your family ID"
              style={{ border: "1px solid #cbd5e1", borderRadius: 8, padding: "0.65rem 0.75rem", minWidth: 220 }}
            />
          </label>
          <button type="button" className="button" onClick={() => void loadTransactions()} disabled={loading}>
            {loading ? "Loading…" : "Load transactions"}
          </button>
        </section>
      )}

      {error && (
        <div role="alert" style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", padding: "0.8rem 1rem", borderRadius: 10, margin: "1rem 0" }}>
          {error}
        </div>
      )}
      {notice && <p role="status" style={{ color: "#047857", fontSize: 14 }}>{notice}</p>}

      <section aria-label="Transaction summary" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12, margin: "1.5rem 0" }}>
        {[
          { label: "Transactions", value: counts.total, color: "#003087" },
          { label: "Completed", value: counts.completed, color: "#15803d" },
          { label: "Refunded / partial", value: counts.refunded, color: "#b45309" },
          { label: "Flagged for review", value: counts.flagged, color: "#b91c1c" },
        ].map((stat) => (
          <div key={stat.label} style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: 12, padding: "1rem" }}>
            <div style={{ color: "#64748b", fontSize: 13 }}>{stat.label}</div>
            <div style={{ color: stat.color, fontSize: 28, fontWeight: 800, marginTop: 4 }}>{stat.value}</div>
          </div>
        ))}
      </section>

      <section style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 12, margin: "1.5rem 0 0.75rem" }}>
        <h2 style={{ color: "#003087", fontSize: 20, margin: 0 }}>Recent activity</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <label htmlFor="status-filter" className="sr-only">Filter transactions</label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            style={{ border: "1px solid #cbd5e1", borderRadius: 8, padding: "0.55rem", background: "white" }}
          >
            <option value="ALL">All statuses</option>
            <option value="REFUNDS">Refunds</option>
            <option value="COMPLETED">Completed</option>
            <option value="FLAGGED">Flagged</option>
            <option value="DISPUTED">Disputed</option>
          </select>
          <button type="button" className="button" onClick={() => void loadTransactions()} disabled={loading || !validFamilyId}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </section>

      <section style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: 16, padding: "0 20px" }}>
        {loading && items.length === 0 ? (
          <p role="status" style={{ color: "#64748b", padding: "1.2rem 0" }}>Loading transaction statuses…</p>
        ) : filteredItems.length === 0 ? (
          <p style={{ color: "#64748b", padding: "1.2rem 0" }}>
            {items.length === 0
              ? "No transactions are available for this family yet. Verified PayPal refund events will appear here when received."
              : "No transactions match this status filter."}
          </p>
        ) : (
          filteredItems.map((item) => {
            const isRefund = refundStatuses.has(item.status);
            const statusStyle = isRefund
              ? { background: "#fff7ed", color: "#9a3412" }
              : item.status === "COMPLETED"
                ? { background: "#dcfce7", color: "#15803d" }
                : item.status === "DISPUTED" || item.is_flagged
                  ? { background: "#fee2e2", color: "#b91c1c" }
                  : { background: "#f1f5f9", color: "#475569" };
            const merchant = item.clean_merchant_name || item.merchant_name || "PayPal transaction";
            return (
              <article key={item.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 14, padding: "1rem 0", borderBottom: "1px solid #eef1ee" }}>
                <div style={{ minWidth: 220, flex: "1 1 300px" }}>
                  <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
                    <strong style={{ color: "#0f172a", fontSize: 16 }}>{merchant}</strong>
                    <span style={{ ...statusStyle, borderRadius: 999, padding: "0.25rem 0.6rem", fontSize: 12, fontWeight: 700 }}>
                      {item.status.replaceAll("_", " ")}
                    </span>
                    {item.is_flagged && (
                      <span style={{ background: "#fef2f2", color: "#b91c1c", borderRadius: 999, padding: "0.25rem 0.6rem", fontSize: 12, fontWeight: 700 }}>
                        FLAGGED
                      </span>
                    )}
                  </div>
                  <div style={{ color: "#64748b", fontSize: 13, marginTop: 6 }}>
                    {item.category || "Uncategorized"} · Transaction #{item.id}
                    {item.created_at ? ` · ${new Date(item.created_at).toLocaleString()}` : ""}
                  </div>
                  {isRefund && (
                    <div style={{ color: "#9a3412", fontSize: 13, marginTop: 6 }}>
                      {item.refund_id
                        ? `PayPal refund reference: ${item.refund_id}`
                        : "Refund status recorded; PayPal reference unavailable."}
                      {" · "}Purchase amount: {new Intl.NumberFormat(undefined, { style: "currency", currency: item.currency }).format(item.amount)}
                    </div>
                  )}
                  {item.flagged_reason && (
                    <div style={{ color: "#b91c1c", fontSize: 13, marginTop: 6 }}>{item.flagged_reason}</div>
                  )}
                </div>
                <strong style={{ whiteSpace: "nowrap" }}>
                  {new Intl.NumberFormat(undefined, { style: "currency", currency: item.currency }).format(item.amount)}
                </strong>
              </article>
            );
          })
        )}
      </section>

    </main>
  );
}
