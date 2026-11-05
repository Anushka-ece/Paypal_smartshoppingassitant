"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "../hooks/use-session";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

interface PurchaseRequestItem {
  id: number;
  family_id: number;
  child_id: number;
  item_name: string;
  store_url: string;
  amount: number;
  currency: string;
  status: string;
  ai_risk_assessment: string | null;
  rejection_reason: string | null;
  paypal_order_id: string | null;
  paypal_approval_url: string | null;
  paypal_capture_id: string | null;
  paypal_payment_status: string | null;
  created_at: string | null;
  updated_at: string | null;
}

type CheckoutResult = Pick<
  PurchaseRequestItem,
  "status" | "paypal_payment_status"
>;

function isPaypalSandboxApprovalUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname === "www.sandbox.paypal.com";
  } catch {
    return false;
  }
}

function paymentMessage(result: CheckoutResult, cancelled: boolean): string {
  if (cancelled || result.status === "CANCELLED") {
    return "PayPal checkout was cancelled. No payment was recorded.";
  }
  if (
    result.status === "EXECUTED" &&
    result.paypal_payment_status === "COMPLETED"
  ) {
    return "PayPal confirmed payment successfully.";
  }
  if (
    result.status === "APPROVED" ||
    result.status === "CAPTURE_PENDING" ||
    result.paypal_payment_status === "PENDING"
  ) {
    return "PayPal is still processing this payment. Refresh the request status shortly.";
  }
  return "PayPal did not complete this payment. Review the request status and try again if available.";
}

export default function RequestsPage() {
  const { session, ready } = useSession();
  const [familyIdInput, setFamilyIdInput] = useState("");
  const [requests, setRequests] = useState<PurchaseRequestItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyRequestId, setBusyRequestId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const processedCheckout = useRef(false);

  useEffect(() => {
    if (session?.family_id) {
      setFamilyIdInput(String(session.family_id));
    }
  }, [session?.family_id]);

  const familyId = session?.family_id ?? Number(familyIdInput);
  const isParent = session?.role.toLowerCase() === "parent";

  const loadRequests = useCallback(async (preserveError = false) => {
    if (!session?.token) {
      setError("Sign in to load purchase requests.");
      return;
    }
    if (!Number.isInteger(familyId) || familyId <= 0) {
      setError("Enter a valid family ID to load its purchase requests.");
      return;
    }

    setLoading(true);
    if (!preserveError) setError(null);
    try {
      const response = await fetch(
        `${apiBase}/api/purchase-requests?family_id=${encodeURIComponent(String(familyId))}`,
        { headers: { Authorization: `Bearer ${session.token}` }, cache: "no-store" },
      );
      const data: unknown = await response.json();
      if (!response.ok) {
        const detail =
          typeof data === "object" &&
          data !== null &&
          "detail" in data &&
          typeof data.detail === "string"
            ? data.detail
            : "Unable to load purchase requests.";
        throw new Error(detail);
      }
      if (!Array.isArray(data)) {
        throw new Error("The purchase request service returned an invalid response.");
      }
      setRequests(data as PurchaseRequestItem[]);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to connect to the purchase request service.",
      );
    } finally {
      setLoading(false);
    }
  }, [familyId, session?.token]);

  useEffect(() => {
    if (ready && session?.token) {
      void loadRequests();
    } else if (ready) {
      setError("Sign in to load purchase requests.");
    }
  }, [ready, session?.token, loadRequests]);

  useEffect(() => {
    if (!ready || processedCheckout.current) return;

    const params = new URLSearchParams(window.location.search);
    const checkout = params.get("checkout");
    const requestId = Number(params.get("request_id"));
    if (
      (checkout !== "return" && checkout !== "cancel") ||
      !Number.isInteger(requestId) ||
      requestId <= 0
    ) {
      return;
    }

    processedCheckout.current = true;
    const token = params.get("token");
    const checkoutState = params.get("checkout_state");
    const processCheckoutReturn = async () => {
      setError(null);
      setNotice(checkout === "cancel" ? "Recording PayPal cancellation…" : "Verifying PayPal payment…");
      try {
        if (!checkoutState) {
          throw new Error("PayPal checkout state is missing. Refresh the request to verify its status.");
        }
        const callbackParams = new URLSearchParams({ checkout_state: checkoutState });
        if (token) callbackParams.set("token", token);
        const endpoint =
          checkout === "cancel"
            ? `${apiBase}/api/purchase-requests/${requestId}/paypal/cancel?${callbackParams.toString()}`
            : token
              ? `${apiBase}/api/purchase-requests/${requestId}/paypal/return?${callbackParams.toString()}`
              : null;
        if (!endpoint) {
          throw new Error("PayPal did not return an order reference. Refresh the request to check its status.");
        }

        const response = await fetch(endpoint, {
          headers: session?.token
            ? { Authorization: `Bearer ${session.token}` }
            : undefined,
          cache: "no-store",
        });
        const data: unknown = await response.json();
        if (!response.ok) {
          const detail =
            typeof data === "object" &&
            data !== null &&
            "detail" in data &&
            typeof data.detail === "string"
              ? data.detail
              : "Unable to verify the PayPal checkout result.";
          throw new Error(detail);
        }
        if (
          typeof data !== "object" ||
          data === null ||
          !("status" in data) ||
          !("paypal_payment_status" in data)
        ) {
          throw new Error("The payment service returned an invalid checkout result.");
        }
        setNotice(
          paymentMessage(
            data as CheckoutResult,
            checkout === "cancel",
          ),
        );
      } catch (checkoutError) {
        setError(
          checkoutError instanceof Error
            ? checkoutError.message
            : "Unable to verify the PayPal checkout result.",
        );
        setNotice(null);
      } finally {
        window.history.replaceState(window.history.state, "", window.location.pathname);
        await loadRequests(true);
      }
    };

    void processCheckoutReturn();
  }, [ready, session?.token, loadRequests]);

  async function runRequestAction(
    request: PurchaseRequestItem,
    action: "approve" | "reject" | "capture",
  ) {
    if (!session?.token) {
      setError("Sign in before managing purchase requests.");
      return;
    }
    setBusyRequestId(request.id);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(
        `${apiBase}/api/purchase-requests/${request.id}/${action}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session.token}`,
            ...(action === "reject" ? { "Content-Type": "application/json" } : {}),
          },
          ...(action === "reject"
            ? { body: JSON.stringify({ reason: "Rejected by parent." }) }
            : {}),
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
            : `Unable to ${action} this purchase request.`;
        throw new Error(detail);
      }
      if (typeof data !== "object" || data === null || !("id" in data)) {
        throw new Error("The purchase request service returned an invalid response.");
      }

      const updatedRequest = data as PurchaseRequestItem;
      setRequests((current) =>
        current.map((item) => (item.id === updatedRequest.id ? updatedRequest : item)),
      );
      if (action === "approve") {
        setNotice(
          updatedRequest.paypal_approval_url
            ? "PayPal approval is ready. Continue to PayPal to authorize this purchase."
            : "The request was approved, but PayPal did not provide an approval link.",
        );
      } else if (action === "reject") {
        setNotice("Purchase request rejected.");
      } else {
        setNotice(paymentMessage(updatedRequest, false));
      }
      await loadRequests(true);
    } catch (actionError) {
      setError(
        actionError instanceof Error
          ? actionError.message
          : `Unable to ${action} this purchase request.`,
      );
      await loadRequests(true);
    } finally {
      setBusyRequestId(null);
    }
  }

  function continueToPaypal(request: PurchaseRequestItem) {
    if (!request.paypal_approval_url || !isPaypalSandboxApprovalUrl(request.paypal_approval_url)) {
      setError("The backend did not return a valid PayPal sandbox approval link.");
      return;
    }
    window.location.assign(request.paypal_approval_url);
  }

  const statusColor = (request: PurchaseRequestItem) => {
    if (
      request.status === "EXECUTED" &&
      request.paypal_payment_status === "COMPLETED"
    ) {
      return { background: "#dcfce7", color: "#15803d" };
    }
    if (["PAYMENT_FAILED", "REJECTED"].includes(request.status)) {
      return { background: "#fee2e2", color: "#b91c1c" };
    }
    if (request.status === "CANCELLED") {
      return { background: "#f1f5f9", color: "#475569" };
    }
    if (["APPROVED", "CAPTURE_PENDING", "ORDER_CREATING"].includes(request.status)) {
      return { background: "#dbeafe", color: "#1d4ed8" };
    }
    return { background: "#fef3c7", color: "#b45309" };
  };

  return (
    <main style={{ maxWidth: 920, margin: "50px auto", padding: 24 }}>
      <div style={{ marginBottom: "1.5rem" }}>
        <p style={{ color: "#75817b", fontSize: 12, letterSpacing: 1 }}>FAMILY PURCHASES</p>
        <h1 style={{ fontFamily: "Manrope, sans-serif", color: "#003087", margin: "0 0 0.5rem" }}>
          Pre-Purchase Store Requests
        </h1>
        <p style={{ margin: 0, color: "#64748b", fontSize: "0.95rem", lineHeight: 1.6 }}>
          Review purchase requests, then continue to PayPal sandbox for secure buyer approval.
          Payment status is reported by the backend after PayPal verification.
        </p>
      </div>

      {!session?.token && ready && (
        <div role="alert" style={{ background: "#fff7e8", border: "1px solid #f3dfb8", color: "#82551c", padding: "0.75rem 1rem", borderRadius: "0.5rem", marginBottom: "1rem" }}>
          <a href="/login" style={{ color: "#82551c", fontWeight: 700 }}>Sign in</a> to view and manage purchase requests.
        </div>
      )}

      {session?.token && !session.family_id && (
        <section style={{ display: "flex", flexWrap: "wrap", alignItems: "end", gap: 10, background: "white", border: "1px solid #e2e8f0", borderRadius: "0.75rem", padding: "1rem", marginBottom: "1rem" }}>
          <label htmlFor="family-id" style={{ display: "grid", gap: 6, color: "#64748b", fontSize: "0.85rem" }}>
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
          <button
            type="button"
            onClick={() => void loadRequests()}
            disabled={loading}
            style={{ background: "#006b52", color: "white", border: 0, padding: "0.7rem 1rem", borderRadius: 8, fontWeight: 700, opacity: loading ? 0.7 : 1 }}
          >
            Load requests
          </button>
        </section>
      )}

      {notice && (
        <div role="status" style={{ background: "#ecfdf5", border: "1px solid #10b981", color: "#065f46", padding: "0.75rem 1rem", borderRadius: "0.5rem", marginBottom: "1rem" }}>
          {notice}
        </div>
      )}
      {error && (
        <div role="alert" style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", padding: "0.75rem 1rem", borderRadius: "0.5rem", marginBottom: "1rem" }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: "1rem", flexWrap: "wrap" }}>
        <h2 style={{ color: "#003087", fontSize: "1.1rem", margin: 0 }}>Requests</h2>
        <button
          type="button"
          onClick={() => void loadRequests()}
          disabled={loading || !session?.token || !Number.isInteger(familyId) || familyId <= 0}
          style={{ background: "white", color: "#003087", border: "1px solid #cbd5e1", padding: "0.55rem 0.9rem", borderRadius: 8, fontWeight: 600, opacity: loading ? 0.7 : 1 }}
        >
          {loading ? "Refreshing…" : "Refresh status"}
        </button>
      </div>

      {loading && requests.length === 0 ? (
        <div role="status" style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "0.75rem", padding: "1.5rem", color: "#64748b" }}>
          Loading purchase requests…
        </div>
      ) : requests.length === 0 ? (
        <div style={{ background: "white", border: "1px dashed #cbd5e1", borderRadius: "0.75rem", padding: "1.5rem", color: "#64748b", textAlign: "center" }}>
          {session?.token && Number.isInteger(familyId) && familyId > 0
            ? "No purchase requests found for this family."
            : "Enter a family ID to view its purchase requests."}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {requests.map((request) => {
            const busy = busyRequestId === request.id;
            const checkoutComplete =
              request.status === "EXECUTED" &&
              request.paypal_payment_status === "COMPLETED";
            return (
              <article
                key={request.id}
                style={{ background: "white", padding: "1.25rem", borderRadius: "0.75rem", border: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}
              >
                <div style={{ minWidth: 0, flex: "1 1 340px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", flexWrap: "wrap" }}>
                    <h3 style={{ fontWeight: 700, fontSize: "1.1rem", margin: 0 }}>{request.item_name}</h3>
                    <span style={{ ...statusColor(request), padding: "0.25rem 0.6rem", borderRadius: 999, fontSize: "0.75rem", fontWeight: 700 }}>
                      {checkoutComplete ? "PAYMENT COMPLETE" : request.status.replaceAll("_", " ")}
                    </span>
                  </div>
                  <div style={{ color: "#64748b", fontSize: "0.9rem", marginTop: "0.5rem", lineHeight: 1.7 }}>
                    <div>Child ID: <strong style={{ color: "#0f172a" }}>{request.child_id}</strong> · Amount: <strong style={{ color: "#0f172a" }}>{new Intl.NumberFormat(undefined, { style: "currency", currency: request.currency }).format(request.amount)}</strong></div>
                    <div>Request #{request.id} · {request.created_at ? new Date(request.created_at).toLocaleString() : "Date unavailable"}</div>
                    {request.paypal_payment_status && (
                      <div>PayPal status: <strong style={{ color: "#0f172a" }}>{request.paypal_payment_status.replaceAll("_", " ")}</strong></div>
                    )}
                    {request.paypal_capture_id && <div>Capture reference: {request.paypal_capture_id}</div>}
                    {request.rejection_reason && <div style={{ color: "#b91c1c" }}>Reason: {request.rejection_reason}</div>}
                  </div>
                  <div style={{ fontSize: "0.85rem", marginTop: "0.5rem", overflowWrap: "anywhere" }}>
                    Store:{" "}
                    <a href={request.store_url} target="_blank" rel="noreferrer" style={{ color: "#0070ba" }}>
                      {request.store_url}
                    </a>
                  </div>
                  {request.ai_risk_assessment && (
                    <div style={{ fontSize: "0.85rem", marginTop: "0.5rem", color: "#a16207", fontWeight: 500 }}>
                      Safety review: {request.ai_risk_assessment}
                    </div>
                  )}
                  {request.status === "APPROVED" && !request.paypal_approval_url && (
                    <div style={{ color: "#a16207", marginTop: 8, fontSize: 13 }}>
                      PayPal approval link is unavailable. Refresh or contact the family administrator.
                    </div>
                  )}
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                  {isParent && request.status === "PENDING_APPROVAL" && (
                    <>
                      <button
                        type="button"
                        onClick={() => void runRequestAction(request, "approve")}
                        disabled={busy}
                        style={{ background: "#10b981", color: "white", border: "none", padding: "0.6rem 1rem", borderRadius: "0.375rem", fontWeight: 600, opacity: busy ? 0.7 : 1 }}
                      >
                        {busy ? "Creating PayPal order…" : "Approve & pay"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void runRequestAction(request, "reject")}
                        disabled={busy}
                        style={{ background: "#ef4444", color: "white", border: "none", padding: "0.6rem 1rem", borderRadius: "0.375rem", fontWeight: 600, opacity: busy ? 0.7 : 1 }}
                      >
                        Reject
                      </button>
                    </>
                  )}
                  {request.status === "APPROVED" && request.paypal_approval_url && (
                    <button
                      type="button"
                      onClick={() => continueToPaypal(request)}
                      style={{ background: "#0070ba", color: "white", border: "none", padding: "0.7rem 1rem", borderRadius: "0.375rem", fontWeight: 700 }}
                    >
                      Continue to PayPal
                    </button>
                  )}
                  {request.status === "PAYMENT_FAILED" && request.paypal_order_id && (
                    <button
                      type="button"
                      onClick={() => void runRequestAction(request, "capture")}
                      disabled={busy}
                      style={{ background: "#a16207", color: "white", border: "none", padding: "0.6rem 1rem", borderRadius: "0.375rem", fontWeight: 600, opacity: busy ? 0.7 : 1 }}
                    >
                      {busy ? "Retrying capture…" : "Retry payment capture"}
                    </button>
                  )}
                  {isParent &&
                    request.status === "PAYMENT_FAILED" &&
                    !request.paypal_order_id && (
                      <button
                        type="button"
                        onClick={() => void runRequestAction(request, "approve")}
                        disabled={busy}
                        style={{ background: "#a16207", color: "white", border: "none", padding: "0.6rem 1rem", borderRadius: "0.375rem", fontWeight: 600, opacity: busy ? 0.7 : 1 }}
                      >
                        {busy ? "Retrying…" : "Retry PayPal setup"}
                      </button>
                    )}
                  {request.status === "CAPTURE_PENDING" && (
                    <span role="status" style={{ color: "#1d4ed8", fontSize: 13, alignSelf: "center" }}>
                      Payment confirmation pending
                    </span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </main>
  );
}
