'use client';

import React, { useState } from 'react';

interface TransactionItem {
  id: number;
  merchant: string;
  amount: number;
  category: string;
  child: string;
  isFlagged: boolean;
  flagReason?: string;
  status: string;
}

export default function DashboardPage() {
  const [transactions, setTransactions] = useState<TransactionItem[]>([
    {
      id: 101,
      merchant: 'Epic Games *Fortnite',
      amount: 49.99,
      category: 'Gaming',
      child: 'Bart Simpson',
      isFlagged: true,
      flagReason: 'Rule Matched: In-game purchase exceeding $25 threshold',
      status: 'FLAGGED',
    },
    {
      id: 102,
      merchant: 'G2A Marketplace',
      amount: 19.99,
      category: 'Gaming',
      child: 'Bart Simpson',
      isFlagged: true,
      flagReason: 'Threat Blacklist: Grey-market digital game key marketplace',
      status: 'FLAGGED',
    },
    {
      id: 103,
      merchant: 'Starbucks Coffee',
      amount: 5.75,
      category: 'Food & Dining',
      child: 'Lisa Simpson',
      isFlagged: false,
      status: 'COMPLETED',
    },
    {
      id: 104,
      merchant: 'Uber *Trip',
      amount: 16.50,
      category: 'Transport',
      child: 'Lisa Simpson',
      isFlagged: false,
      status: 'COMPLETED',
    },
  ]);

  const [message, setMessage] = useState<string | null>(null);

  const handleApprove = (id: number) => {
    setTransactions((prev) =>
      prev.map((t) => (t.id === id ? { ...t, isFlagged: false, status: 'COMPLETED' } : t))
    );
    setMessage(`Transaction #${id} approved by parent.`);
  };

  const handleFlagForReview = (id: number) => {
    setTransactions((prev) =>
      prev.map((t) => (t.id === id ? { ...t, status: 'NEEDS_EXPLANATION' } : t))
    );
    setMessage(`Requested receipt upload and explanation from child for Transaction #${id}.`);
  };

  const handleDisputeAndFreeze = (id: number) => {
    setTransactions((prev) =>
      prev.map((t) => (t.id === id ? { ...t, status: 'DISPUTED_AND_FROZEN' } : t))
    );
    setMessage(`Dispute initiated! Upcoming allowances frozen. Redirecting to PayPal Resolution Center...`);
    window.open('https://www.paypal.com/disputes/', '_blank');
  };

  return (
    <div>
      <h2 style={{ fontSize: '1.8rem', margin: '0 0 1.5rem 0', color: '#003087' }}>Parent Financial Overview</h2>

      {message && (
        <div style={{ backgroundColor: '#ecfdf5', border: '1px solid #10b981', color: '#065f46', padding: '0.75rem 1rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
          {message}
        </div>
      )}

      {/* Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div style={{ background: 'white', padding: '1.25rem', borderRadius: '0.5rem', border: '1px solid #e2e8f0' }}>
          <div style={{ color: '#64748b', fontSize: '0.85rem', fontWeight: 600 }}>TOTAL FAMILY SPEND</div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#003087', marginTop: '0.25rem' }}>$412.50</div>
        </div>
        <div style={{ background: 'white', padding: '1.25rem', borderRadius: '0.5rem', border: '1px solid #e2e8f0' }}>
          <div style={{ color: '#64748b', fontSize: '0.85rem', fontWeight: 600 }}>PARENT WALLET BALANCE</div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#10b981', marginTop: '0.25rem' }}>$1,250.00</div>
        </div>
        <div style={{ background: 'white', padding: '1.25rem', borderRadius: '0.5rem', border: '1px solid #e2e8f0' }}>
          <div style={{ color: '#64748b', fontSize: '0.85rem', fontWeight: 600 }}>CHILD ALLOWANCE POOL</div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0284c7', marginTop: '0.25rem' }}>$75.00</div>
        </div>
        <div style={{ background: 'white', padding: '1.25rem', borderRadius: '0.5rem', border: '1px solid #e2e8f0' }}>
          <div style={{ color: '#64748b', fontSize: '0.85rem', fontWeight: 600 }}>FLAGGED INCIDENTS</div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#ef4444', marginTop: '0.25rem' }}>
            {transactions.filter((t) => t.isFlagged).length}
          </div>
        </div>
      </div>

      {/* Flagged Incidents Alert Section */}
      <h3 style={{ fontSize: '1.3rem', color: '#991b1b', marginBottom: '1rem' }}>🚨 Flagged Transaction Alerts Requiring Attention</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2.5rem' }}>
        {transactions.filter((t) => t.isFlagged).length === 0 ? (
          <div style={{ background: 'white', padding: '1.5rem', borderRadius: '0.5rem', border: '1px dashed #cbd5e1', textAlign: 'center', color: '#64748b' }}>
            ✅ No flagged transactions. All child spending complies with parent guardrails.
          </div>
        ) : (
          transactions
            .filter((t) => t.isFlagged)
            .map((t) => (
              <div
                key={t.id}
                style={{
                  background: '#fff',
                  borderLeft: '5px solid #ef4444',
                  border: '1px solid #fed7aa',
                  borderRadius: '0.5rem',
                  padding: '1.25rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '1rem',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '1.1rem' }}>{t.merchant}</span>
                    <span style={{ background: '#fee2e2', color: '#991b1b', fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '0.25rem', fontWeight: 700 }}>
                      HIGH RISK
                    </span>
                  </div>
                  <div style={{ color: '#64748b', fontSize: '0.9rem', marginTop: '0.25rem' }}>
                    Spender: <strong>{t.child}</strong> | Amount: <strong style={{ color: '#0f172a' }}>${t.amount.toFixed(2)}</strong> | Category: {t.category}
                  </div>
                  <div style={{ color: '#b91c1c', fontSize: '0.85rem', marginTop: '0.5rem', fontWeight: 500 }}>
                    ⚠️ {t.flagReason}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    onClick={() => handleApprove(t.id)}
                    style={{ background: '#10b981', color: 'white', border: 'none', padding: '0.5rem 0.85rem', borderRadius: '0.375rem', fontWeight: 600, cursor: 'pointer' }}
                  >
                    [Approve]
                  </button>
                  <button
                    onClick={() => handleFlagForReview(t.id)}
                    style={{ background: '#f59e0b', color: 'white', border: 'none', padding: '0.5rem 0.85rem', borderRadius: '0.375rem', fontWeight: 600, cursor: 'pointer' }}
                  >
                    [Flag for Review]
                  </button>
                  <button
                    onClick={() => handleDisputeAndFreeze(t.id)}
                    style={{ background: '#ef4444', color: 'white', border: 'none', padding: '0.5rem 0.85rem', borderRadius: '0.375rem', fontWeight: 600, cursor: 'pointer' }}
                  >
                    [Dispute / Freeze]
                  </button>
                </div>
              </div>
            ))
        )}
      </div>

      {/* Recent Transactions Ledger */}
      <h3 style={{ fontSize: '1.3rem', color: '#003087', marginBottom: '1rem' }}>All Recent Family Transactions</h3>
      <div style={{ background: 'white', borderRadius: '0.5rem', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.95rem' }}>
          <thead>
            <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>
              <th style={{ padding: '0.75rem 1rem' }}>Merchant</th>
              <th style={{ padding: '0.75rem 1rem' }}>Family Member</th>
              <th style={{ padding: '0.75rem 1rem' }}>Category</th>
              <th style={{ padding: '0.75rem 1rem' }}>Amount</th>
              <th style={{ padding: '0.75rem 1rem' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((t) => (
              <tr key={t.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                <td style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>{t.merchant}</td>
                <td style={{ padding: '0.75rem 1rem' }}>{t.child}</td>
                <td style={{ padding: '0.75rem 1rem' }}>{t.category}</td>
                <td style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>${t.amount.toFixed(2)}</td>
                <td style={{ padding: '0.75rem 1rem' }}>
                  <span
                    style={{
                      padding: '0.2rem 0.5rem',
                      borderRadius: '0.25rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      background: t.status === 'COMPLETED' ? '#dcfce7' : t.status === 'FLAGGED' ? '#fee2e2' : '#fef3c7',
                      color: t.status === 'COMPLETED' ? '#15803d' : t.status === 'FLAGGED' ? '#b91c1c' : '#b45309',
                    }}
                  >
                    {t.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
