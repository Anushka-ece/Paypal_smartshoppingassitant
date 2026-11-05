'use client';

import React, { type FormEvent, useCallback, useEffect, useState } from 'react';
import { useSession } from '../hooks/use-session';

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? '';
const refundStatuses = new Set(['REFUNDED', 'PARTIALLY_REFUNDED']);

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
  status: string;
  date: string;
}

export default function BudgetsPage() {
  const { session, ready } = useSession();
  const [hideRefunded, setHideRefunded] = useState<boolean>(false);
  const [envelopes, setEnvelopes] = useState<Envelope[]>([]);
  const [ledger, setLedger] = useState<BudgetItem[]>([]);
  const [budgetName, setBudgetName] = useState('Food & Dining');
  const [allocatedAmount, setAllocatedAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const familyId = session?.family_id;
  const isParent = session?.role.toUpperCase() === 'PARENT' || session?.role.toUpperCase() === 'CO_PARENT';

  const loadData = useCallback(async () => {
    if (!session?.token || !familyId) {
      setError('Sign in to view your family budgets and transactions.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const headers = { Authorization: `Bearer ${session.token}` };
      const [budgetResponse, transactionResponse] = await Promise.all([
        fetch(`${apiBase}/api/budgets/envelopes?family_id=${familyId}`, { headers, cache: 'no-store' }),
        fetch(`${apiBase}/api/transactions?family_id=${familyId}&limit=200`, { headers, cache: 'no-store' }),
      ]);
      const budgetData = await budgetResponse.json();
      const transactionData = await transactionResponse.json();
      if (!budgetResponse.ok || !transactionResponse.ok) {
        const detail = [budgetData, transactionData].find(
          (value) => typeof value === 'object' && value !== null && 'detail' in value,
        )?.detail;
        throw new Error(typeof detail === 'string' ? detail : 'Unable to load family finances.');
      }
      if (!Array.isArray(budgetData) || !Array.isArray(transactionData)) {
        throw new Error('The finance service returned an invalid response.');
      }

      setEnvelopes(
        budgetData.map((item) => ({
          id: item.id,
          name: item.name,
          allocated: item.allocated_amount,
          spent: item.current_spent,
          currency: item.currency,
        })),
      );
      setLedger(
        transactionData.map((item) => ({
          id: item.id,
          merchant: item.clean_merchant_name || item.merchant_name || 'Expense',
          category: item.category || 'Uncategorized',
          amount: item.amount,
          status: item.status,
          date: item.created_at ? new Date(item.created_at).toLocaleDateString() : '—',
        })),
      );
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load family finances.');
    } finally {
      setLoading(false);
    }
  }, [familyId, session?.token]);

  useEffect(() => {
    if (ready && session?.token) void loadData();
    else if (ready) setError('Sign in to view your family budgets and transactions.');
  }, [ready, session?.token, loadData]);

  async function createBudget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session?.token || !familyId) {
      setError('Sign in to create a family budget.');
      return;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(`${apiBase}/api/budgets/envelopes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.token}`,
        },
        body: JSON.stringify({
          family_id: familyId,
          name: budgetName,
          allocated_amount: Number(allocatedAmount),
          currency: 'USD',
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? 'Unable to create this budget.');
      setAllocatedAmount('');
      await loadData();
      setNotice('Budget created. Matching expenses will update its spending total.');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to create this budget.');
    } finally {
      setSaving(false);
    }
  }

  const filteredLedger = hideRefunded
    ? ledger.filter((item) => !refundStatuses.has(item.status))
    : ledger;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.8rem', margin: '0 0 0.25rem 0', color: '#003087' }}>Virtual Envelope Budgets</h2>
          <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
            Create category budgets and track them against expenses recorded by your family.
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

      {!session?.token && ready && <p role="alert">Sign in to manage family budgets. <a href="/login">Go to login</a>.</p>}
      {error && <div role="alert" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', padding: '0.85rem 1rem', borderRadius: '0.5rem', marginBottom: '1rem' }}>{error}</div>}
      {notice && <p role="status" style={{ color: '#047857' }}>{notice}</p>}

      {session?.token && isParent && (
        <form onSubmit={createBudget} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'end', gap: '0.75rem', background: 'white', padding: '1rem', borderRadius: '0.5rem', border: '1px solid #e2e8f0', marginBottom: '1.5rem' }}>
          <label style={{ display: 'grid', gap: 6, color: '#64748b', fontSize: 14 }}>
            Category
            <select value={budgetName} onChange={(event) => setBudgetName(event.target.value)} style={{ border: '1px solid #cbd5e1', borderRadius: 8, padding: '0.65rem 0.75rem', background: 'white' }}>
              {['Food & Dining', 'Groceries', 'Transport', 'Shopping', 'Gaming', 'Entertainment', 'Health', 'Education', 'Other'].map((name) => <option key={name}>{name}</option>)}
            </select>
          </label>
          <label style={{ display: 'grid', gap: 6, color: '#64748b', fontSize: 14 }}>
            Budget limit (USD)
            <input required min="0.01" step="0.01" type="number" value={allocatedAmount} onChange={(event) => setAllocatedAmount(event.target.value)} placeholder="e.g. 150.00" style={{ border: '1px solid #cbd5e1', borderRadius: 8, padding: '0.65rem 0.75rem' }} />
          </label>
          <button type="submit" className="button" disabled={saving}>{saving ? 'Saving…' : 'Create budget'}</button>
        </form>
      )}

      {/* Progress Bars for Envelopes */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(270px, 1fr))', gap: '1.25rem', marginBottom: '2.5rem' }}>
        {!loading && session?.token && envelopes.length === 0 && (
          <p style={{ color: '#64748b' }}>No budgets yet. Create a category budget to start tracking spending.</p>
        )}
        {envelopes.map((env) => {
          const percent = env.allocated > 0 ? Math.min(100, Math.round((env.spent / env.allocated) * 100)) : 0;
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
            {!loading && filteredLedger.length === 0 && (
              <tr><td colSpan={5} style={{ padding: '1rem', color: '#64748b' }}>No family expenses recorded yet. Add one from the Transactions page.</td></tr>
            )}
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
