'use client';

import React from 'react';

export default function HomePage() {
  return (
    <main>
      <div style={{ background: 'linear-gradient(135deg, #0070ba 0%, #003087 100%)', color: 'white', borderRadius: '1rem', padding: '2.5rem', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2.2rem', margin: '0 0 0.75rem 0' }}>Welcome to PayPal Family Budgeting</h1>
        <p style={{ fontSize: '1.1rem', margin: 0, opacity: 0.9 }}>
          Intelligent financial oversight, double-entry ledger security, and natural language AI guardrails powered by Google Gemini.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
        <a href="/dashboard" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div style={{ background: 'white', padding: '1.75rem', borderRadius: '0.75rem', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#003087', margin: '0 0 0.5rem 0' }}>📊 Parent Overview Dashboard</h3>
            <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
              Track real-time family spend, account balances, and action suspicious transactions within seconds.
            </p>
          </div>
        </a>

        <a href="/budgets" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div style={{ background: 'white', padding: '1.75rem', borderRadius: '0.75rem', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#003087', margin: '0 0 0.5rem 0' }}>✉️ Virtual Envelope Budgets</h3>
            <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
              Categorized envelope balances with automated net-zero refund reconciliation.
            </p>
          </div>
        </a>

        <a href="/guardrails" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div style={{ background: 'white', padding: '1.75rem', borderRadius: '0.75rem', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#003087', margin: '0 0 0.5rem 0' }}>🛡️ Natural Language Guardrails</h3>
            <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
              Set rules in plain English: "Flag video games over $25" or "Block unverified digital key stores".
            </p>
          </div>
        </a>

        <a href="/guardrails/simulator" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div style={{ background: 'white', padding: '1.75rem', borderRadius: '0.75rem', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#003087', margin: '0 0 0.5rem 0' }}>🧪 Policy Rule Simulator</h3>
            <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
              Test draft natural language rules against transactions and view risk scores in real-time.
            </p>
          </div>
        </a>

        <a href="/requests" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div style={{ background: 'white', padding: '1.75rem', borderRadius: '0.75rem', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#003087', margin: '0 0 0.5rem 0' }}>🛍️ Pre-Purchase Approval Queue</h3>
            <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
              Review child item purchase requests with AI store safety checks and 1-tap checkout.
            </p>
          </div>
        </a>

        <a href="/family" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div style={{ background: 'white', padding: '1.75rem', borderRadius: '0.75rem', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#003087', margin: '0 0 0.5rem 0' }}>👨‍👩‍👧‍👦 Family Member Management</h3>
            <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
              Generate secure invite tokens for co-parents, teens, and children with COPPA compliance.
            </p>
          </div>
        </a>
      </div>
    </main>
  );
}
