'use client';

import React, { useState } from 'react';

interface Envelope {
  id: number;
  name: string;
  allocated: number;
  spent: number;
  currency: string;
}

interface BudgetItem {
  id: number;
  merchant: string;
  category: string;
  amount: number;
  status: 'COMPLETED' | 'REFUNDED' | 'PARTIALLY_REFUNDED';
  date: string;
}

export default function BudgetsPage() {
  const [hideRefunded, setHideRefunded] = useState<boolean>(false);

  const [envelopes, setEnvelopes] = useState<Envelope[]>([
    { id: 1, name: 'Gaming & In-App Purchases', allocated: 100.0, spent: 49.99, currency: 'USD' },
    { id: 2, name: 'Food & Dining Out', allocated: 150.0, spent: 85.5, currency: 'USD' },
    { id: 3, name: 'Transport & Rideshare', allocated: 80.0, spent: 32.0, currency: 'USD' },
    { id: 4, name: 'Shopping & Apparel', allocated: 120.0, spent: 110.0, currency: 'USD' },
  ]);

  const [ledger, setLedger] = useState<BudgetItem[]>([
    { id: 201, merchant: 'Steam Games', category: 'Gaming & In-App Purchases', amount: 49.99, status: 'COMPLETED', date: '2026-10-30' },
    { id: 202, merchant: 'McDonalds', category: 'Food & Dining Out', amount: 14.50, status: 'COMPLETED', date: '2026-10-29' },
    { id: 203, merchant: 'Target Store', category: 'Shopping & Apparel', amount: 65.00, status: 'REFUNDED', date: '2026-10-28' },
    { id: 204, merchant: 'Uber *Trip', category: 'Transport & Rideshare', amount: 18.00, status: 'COMPLETED', date: '2026-10-28' },
    { id: 205, merchant: 'Amazon Marketplace', category: 'Shopping & Apparel', amount: 45.00, status: 'PARTIALLY_REFUNDED', date: '2026-10-27' },
  ]);

  const filteredLedger = hideRefunded
    ? ledger.filter((item) => item.status === 'COMPLETED')
    : ledger;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.8rem', margin: '0 0 0.25rem 0', color: '#003087' }}>Virtual Envelope Budgets</h2>
          <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
            Allocated category balances with automated refund net-zero reconciliation.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'white', padding: '0.5rem 1rem', borderRadius: '0.5rem', border: '1px solid #cbd5e1' }}>
          <input
            id="hide-refund-toggle"
            type="checkbox"
            checked={hideRefunded}
            onChange={(e) => setHideRefunded(e.target.checked)}
            style={{ width: '1.1rem', height: '1.1rem', cursor: 'pointer' }}
          />
          <label htmlFor="hide-refund-toggle" style={{ fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer' }}>
            Hide refunded transactions
          </label>
        </div>
      </div>

      {/* Progress Bars for Envelopes */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(270px, 1fr))', gap: '1.25rem', marginBottom: '2.5rem' }}>
        {envelopes.map((env) => {
          const percent = Math.min(100, Math.round((env.spent / env.allocated) * 100));
          const isWarning = percent >= 80;
          return (
            <div key={env.id} style={{ background: 'white', padding: '1.25rem', borderRadius: '0.5rem', border: '1px solid #e2e8f0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, marginBottom: '0.5rem' }}>
                <span>{env.name}</span>
                <span style={{ color: isWarning ? '#ef4444' : '#10b981' }}>{percent}%</span>
              </div>
              <div style={{ background: '#f1f5f9', height: '10px', borderRadius: '5px', overflow: 'hidden', marginBottom: '0.75rem' }}>
                <div
                  style={{
                    width: `${percent}%`,
                    height: '100%',
                    background: isWarning ? '#ef4444' : '#0070ba',
                    borderRadius: '5px',
                    transition: 'width 0.3s ease',
                  }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#64748b' }}>
                <span>Spent: ${env.spent.toFixed(2)}</span>
                <span>Limit: ${env.allocated.toFixed(2)}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Category Transactions Ledger Table */}
      <h3 style={{ fontSize: '1.3rem', color: '#003087', marginBottom: '1rem' }}>Envelope Transaction Ledger</h3>
      <div style={{ background: 'white', borderRadius: '0.5rem', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.95rem' }}>
          <thead>
            <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>
              <th style={{ padding: '0.75rem 1rem' }}>Date</th>
              <th style={{ padding: '0.75rem 1rem' }}>Merchant</th>
              <th style={{ padding: '0.75rem 1rem' }}>Envelope</th>
              <th style={{ padding: '0.75rem 1rem' }}>Amount</th>
              <th style={{ padding: '0.75rem 1rem' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredLedger.map((item) => (
              <tr key={item.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                <td style={{ padding: '0.75rem 1rem', color: '#64748b' }}>{item.date}</td>
                <td style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>{item.merchant}</td>
                <td style={{ padding: '0.75rem 1rem' }}>{item.category}</td>
                <td style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>${item.amount.toFixed(2)}</td>
                <td style={{ padding: '0.75rem 1rem' }}>
                  <span
                    style={{
                      padding: '0.2rem 0.5rem',
                      borderRadius: '0.25rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      background:
                        item.status === 'COMPLETED'
                          ? '#dcfce7'
                          : item.status === 'REFUNDED'
                          ? '#f1f5f9'
                          : '#fef3c7',
                      color:
                        item.status === 'COMPLETED'
                          ? '#15803d'
                          : item.status === 'REFUNDED'
                          ? '#64748b'
                          : '#b45309',
                    }}
                  >
                    {item.status}
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
