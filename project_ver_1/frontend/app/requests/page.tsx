'use client';

import React, { useState } from 'react';

interface PurchaseRequestItem {
  id: number;
  child: string;
  itemName: string;
  storeUrl: string;
  amount: number;
  status: 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED';
  safetyScan: string;
  date: string;
}

export default function RequestsPage() {
  const [requests, setRequests] = useState<PurchaseRequestItem[]>([
    {
      id: 301,
      child: 'Bart Simpson',
      itemName: 'Roblox Digital Gift Card',
      storeUrl: 'https://roblox.com/redeem',
      amount: 15.00,
      status: 'PENDING_APPROVAL',
      safetyScan: 'Safe Merchant (Official store verified)',
      date: '2026-10-31',
    },
    {
      id: 302,
      child: 'Lisa Simpson',
      itemName: 'Saxophone Practice Book PDF',
      storeUrl: 'https://sheetmusicplus.example.com',
      amount: 18.50,
      status: 'PENDING_APPROVAL',
      safetyScan: 'Safe Merchant (Education/Books)',
      date: '2026-10-30',
    },
    {
      id: 303,
      child: 'Bart Simpson',
      itemName: 'Discount Steam Key Pack',
      storeUrl: 'https://g2a.example.com/keys',
      amount: 29.99,
      status: 'PENDING_APPROVAL',
      safetyScan: '⚠️ Warning: Grey-market key store flagged by threat intelligence',
      date: '2026-10-29',
    },
  ]);

  const [notification, setNotification] = useState<string | null>(null);

  const handleApprove = (id: number) => {
    setRequests((prev) =>
      prev.map((r) => (r.id === id ? { ...r, status: 'APPROVED' } : r))
    );
    setNotification(`Approved Request #${id}. PayPal Vault pre-approval order generated.`);
  };

  const handleReject = (id: number) => {
    setRequests((prev) =>
      prev.map((r) => (r.id === id ? { ...r, status: 'REJECTED' } : r))
    );
    setNotification(`Rejected Request #${id}. Notification sent to child.`);
  };

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.8rem', margin: '0 0 0.25rem 0', color: '#003087' }}>Pre-Purchase Store Requests</h2>
        <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
          Children submit purchase links before buying. Review store safety scores and approve with 1 tap.
        </p>
      </div>

      {notification && (
        <div style={{ background: '#ecfdf5', border: '1px solid #10b981', color: '#065f46', padding: '0.75rem 1rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
          {notification}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {requests.map((req) => (
          <div
            key={req.id}
            style={{
              background: 'white',
              padding: '1.5rem',
              borderRadius: '0.5rem',
              border: '1px solid #e2e8f0',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '1rem',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ fontWeight: 700, fontSize: '1.15rem' }}>{req.itemName}</span>
                <span
                  style={{
                    padding: '0.2rem 0.5rem',
                    borderRadius: '0.25rem',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    background:
                      req.status === 'APPROVED'
                        ? '#dcfce7'
                        : req.status === 'REJECTED'
                        ? '#fee2e2'
                        : '#fef3c7',
                    color:
                      req.status === 'APPROVED'
                        ? '#15803d'
                        : req.status === 'REJECTED'
                        ? '#b91c1c'
                        : '#b45309',
                  }}
                >
                  {req.status}
                </span>
              </div>
              <div style={{ color: '#64748b', fontSize: '0.9rem', marginTop: '0.35rem' }}>
                Requested by <strong>{req.child}</strong> | Amount: <strong style={{ color: '#0f172a' }}>${req.amount.toFixed(2)}</strong> | Date: {req.date}
              </div>
              <div style={{ fontSize: '0.85rem', marginTop: '0.35rem' }}>
                Store Link:{' '}
                <a href={req.storeUrl} target="_blank" rel="noreferrer" style={{ color: '#0070ba' }}>
                  {req.storeUrl}
                </a>
              </div>
              <div style={{ fontSize: '0.85rem', marginTop: '0.35rem', color: req.safetyScan.includes('Warning') ? '#b91c1c' : '#15803d', fontWeight: 500 }}>
                {req.safetyScan}
              </div>
            </div>

            {req.status === 'PENDING_APPROVAL' && (
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  onClick={() => handleApprove(req.id)}
                  style={{ background: '#10b981', color: 'white', border: 'none', padding: '0.6rem 1.1rem', borderRadius: '0.375rem', fontWeight: 600, cursor: 'pointer' }}
                >
                  Approve & Pay
                </button>
                <button
                  onClick={() => handleReject(req.id)}
                  style={{ background: '#ef4444', color: 'white', border: 'none', padding: '0.6rem 1.1rem', borderRadius: '0.375rem', fontWeight: 600, cursor: 'pointer' }}
                >
                  Reject
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
