'use client';

import React, { useState } from 'react';

export default function SimulatorPage() {
  const [ruleInput, setRuleInput] = useState('Flag any purchase over $25 on video games or in-game content.');
  const [merchant, setMerchant] = useState('Epic Games Store');
  const [amount, setAmount] = useState('49.99');
  const [category, setCategory] = useState('Gaming');
  const [description, setDescription] = useState('Fortnite V-Bucks Deluxe Edition');

  const [isLoading, setIsLoading] = useState(false);
  const [simulationResult, setSimulationResult] = useState<any>({
    is_flagged: true,
    risk_level: 'HIGH',
    matched_rules: ['Flag any purchase over $25 on video games or in-game content.'],
    summary_for_parent: 'Epic Games Store purchase of $49.99 exceeds your $25 gaming threshold.',
    requires_immediate_action: true,
  });

  const handleRunSimulation = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    setTimeout(() => {
      const parsedAmount = parseFloat(amount) || 0.0;
      const lowerRule = ruleInput.toLowerCase();
      const lowerCategory = category.toLowerCase();

      let flagged = false;
      let matched: string[] = [];
      let reason = 'Purchase complies with tested rules.';

      if (lowerRule.includes('over $25') && parsedAmount > 25) {
        if (lowerCategory.includes('game') || lowerCategory.includes('gaming')) {
          flagged = true;
          matched.push(ruleInput);
          reason = `${merchant} purchase of $${parsedAmount.toFixed(2)} exceeds your $25 gaming limit.`;
        }
      } else if (lowerRule.includes('crypto') && merchant.toLowerCase().includes('crypto')) {
        flagged = true;
        matched.push(ruleInput);
        reason = `Merchant '${merchant}' matched high-risk entity policy.`;
      }

      setSimulationResult({
        is_flagged: flagged,
        risk_level: flagged ? (parsedAmount > 50 ? 'HIGH' : 'MEDIUM') : 'LOW',
        matched_rules: matched,
        summary_for_parent: reason,
        requires_immediate_action: flagged,
      });
      setIsLoading(false);
    }, 400);
  };

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.8rem', margin: '0 0 0.25rem 0', color: '#003087' }}>Policy Rule Simulator & Sandbox</h2>
        <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
          Test draft natural language rules against transactions and inspect real-time AI risk evaluation JSON.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '2rem' }}>
        {/* Input Form */}
        <div style={{ background: 'white', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #e2e8f0' }}>
          <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.2rem', color: '#003087' }}>Simulation Inputs</h3>
          <form onSubmit={handleRunSimulation} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                Draft Natural Language Rule:
              </label>
              <textarea
                value={ruleInput}
                onChange={(e) => setRuleInput(e.target.value)}
                rows={3}
                style={{ width: '100%', padding: '0.5rem', borderRadius: '0.375rem', border: '1px solid #cbd5e1', fontSize: '0.9rem', boxSizing: 'border-box' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                Test Merchant Name:
              </label>
              <input
                type="text"
                value={merchant}
                onChange={(e) => setMerchant(e.target.value)}
                style={{ width: '100%', padding: '0.5rem', borderRadius: '0.375rem', border: '1px solid #cbd5e1', fontSize: '0.9rem', boxSizing: 'border-box' }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                  Amount ($):
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '0.375rem', border: '1px solid #cbd5e1', fontSize: '0.9rem', boxSizing: 'border-box' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                  Category:
                </label>
                <input
                  type="text"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '0.375rem', border: '1px solid #cbd5e1', fontSize: '0.9rem', boxSizing: 'border-box' }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                Description:
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                style={{ width: '100%', padding: '0.5rem', borderRadius: '0.375rem', border: '1px solid #cbd5e1', fontSize: '0.9rem', boxSizing: 'border-box' }}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              style={{
                background: '#0070ba',
                color: 'white',
                border: 'none',
                padding: '0.75rem',
                borderRadius: '0.375rem',
                fontWeight: 700,
                cursor: 'pointer',
                marginTop: '0.5rem',
              }}
            >
              {isLoading ? 'Running LLM Evaluation...' : '⚡ Test Rule against Transaction'}
            </button>
          </form>
        </div>

        {/* Live Output Inspector */}
        <div style={{ background: '#0f172a', color: '#f8fafc', padding: '1.5rem', borderRadius: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#38bdf8' }}>AI Evaluation Output (JSON)</h3>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                padding: '0.2rem 0.6rem',
                borderRadius: '0.25rem',
                background: simulationResult?.is_flagged ? '#ef4444' : '#10b981',
                color: 'white',
              }}
            >
              {simulationResult?.is_flagged ? 'FLAGGED' : 'PASSED'}
            </span>
          </div>

          <pre style={{ margin: 0, background: '#1e293b', padding: '1rem', borderRadius: '0.375rem', overflowX: 'auto', fontSize: '0.85rem', color: '#a5f3fc', lineHeight: 1.5 }}>
            {JSON.stringify(simulationResult, null, 2)}
          </pre>

          <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#1e293b', borderRadius: '0.375rem', borderLeft: `4px solid ${simulationResult?.is_flagged ? '#ef4444' : '#10b981'}` }}>
            <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#e2e8f0' }}>Parent Notification Preview:</div>
            <div style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '0.25rem' }}>
              {simulationResult?.summary_for_parent}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
