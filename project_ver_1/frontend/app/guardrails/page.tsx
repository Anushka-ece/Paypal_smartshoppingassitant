'use client';

import React, { useState } from 'react';

interface PolicyRule {
  id: number;
  text: string;
  isActive: boolean;
  category: string;
}

export default function GuardrailsPage() {
  const [rules, setRules] = useState<PolicyRule[]>([
    { id: 1, text: 'Flag any purchase over $25 on video games or in-game content.', isActive: true, category: 'Gaming' },
    { id: 2, text: 'Block unverified grey-market digital key marketplaces (G2A, Kinguin).', isActive: true, category: 'Threats' },
    { id: 3, text: 'Flag any transactions made past 10:00 PM on school nights.', isActive: true, category: 'Time Restrictions' },
    { id: 4, text: 'Require manual review for any purchase at coffee shops exceeding $12.', isActive: false, category: 'Food & Dining' },
  ]);

  const [newRule, setNewRule] = useState('');

  const handleToggle = (id: number) => {
    setRules((prev) =>
      prev.map((r) => (r.id === id ? { ...r, isActive: !r.isActive } : r))
    );
  };

  const handleAddRule = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRule.trim()) return;
    const rule: PolicyRule = {
      id: Date.now(),
      text: newRule.trim(),
      isActive: true,
      category: 'Custom Rule',
    };
    setRules([rule, ...rules]);
    setNewRule('');
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.8rem', margin: '0 0 0.25rem 0', color: '#003087' }}>Natural Language Guardrail Policies</h2>
          <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
            Set plain-English financial guardrails evaluated in real time by Google Gemini Flash.
          </p>
        </div>
        <a
          href="/guardrails/simulator"
          style={{
            background: '#0070ba',
            color: 'white',
            padding: '0.6rem 1.2rem',
            borderRadius: '0.5rem',
            textDecoration: 'none',
            fontWeight: 600,
            fontSize: '0.9rem',
          }}
        >
          🧪 Open Rule Simulator
        </a>
      </div>

      {/* Add New Rule Form */}
      <form onSubmit={handleAddRule} style={{ background: 'white', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #e2e8f0', marginBottom: '2rem' }}>
        <h3 style={{ margin: '0 0 0.75rem 0', fontSize: '1.1rem' }}>Add New Plain-English Guardrail</h3>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <input
            type="text"
            placeholder="e.g. Flag any purchase over $15 on fast food delivery or peer-to-peer transfers..."
            value={newRule}
            onChange={(e) => setNewRule(e.target.value)}
            style={{
              flex: 1,
              padding: '0.75rem',
              borderRadius: '0.375rem',
              border: '1px solid #cbd5e1',
              fontSize: '0.95rem',
            }}
          />
          <button
            type="submit"
            style={{
              background: '#003087',
              color: 'white',
              border: 'none',
              padding: '0 1.5rem',
              borderRadius: '0.375rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Save Rule
          </button>
        </div>
      </form>

      {/* Active Rules List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {rules.map((rule) => (
          <div
            key={rule.id}
            style={{
              background: 'white',
              padding: '1.25rem',
              borderRadius: '0.5rem',
              border: '1px solid #e2e8f0',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              opacity: rule.isActive ? 1 : 0.6,
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <span style={{ fontWeight: 600, fontSize: '1rem', color: '#0f172a' }}>{rule.text}</span>
                <span style={{ fontSize: '0.75rem', background: '#f1f5f9', padding: '0.2rem 0.5rem', borderRadius: '0.25rem', color: '#475569' }}>
                  {rule.category}
                </span>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                Status: {rule.isActive ? '🟢 Active & Enforcing' : '⚪ Paused'}
              </div>
            </div>

            <button
              onClick={() => handleToggle(rule.id)}
              style={{
                background: rule.isActive ? '#fee2e2' : '#ecfdf5',
                color: rule.isActive ? '#991b1b' : '#065f46',
                border: 'none',
                padding: '0.4rem 0.85rem',
                borderRadius: '0.375rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {rule.isActive ? 'Deactivate' : 'Activate'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
