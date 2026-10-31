import React from 'react';

export const metadata = {
  title: 'PayPal Family Budgeting & AI Guardrails',
  description: 'AI-Powered Family Financial Management Platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: 'system-ui, -apple-system, sans-serif', backgroundColor: '#f8fafc', color: '#0f172a' }}>
        <header style={{ backgroundColor: '#003087', color: 'white', padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.4rem', fontWeight: 800, letterSpacing: '-0.5px' }}>PayPal</span>
            <span style={{ fontSize: '1rem', opacity: 0.85, borderLeft: '1px solid rgba(255,255,255,0.3)', paddingLeft: '0.75rem' }}>Family Budget & Guardrails</span>
          </div>
          <nav style={{ display: 'flex', gap: '1.25rem', fontSize: '0.95rem' }}>
            <a href="/dashboard" style={{ color: 'white', textDecoration: 'none', fontWeight: 500 }}>Dashboard</a>
            <a href="/budgets" style={{ color: 'white', textDecoration: 'none', fontWeight: 500 }}>Envelopes & Budgets</a>
            <a href="/guardrails" style={{ color: 'white', textDecoration: 'none', fontWeight: 500 }}>AI Guardrails</a>
            <a href="/guardrails/simulator" style={{ color: 'white', textDecoration: 'none', fontWeight: 500 }}>Rule Simulator</a>
            <a href="/requests" style={{ color: 'white', textDecoration: 'none', fontWeight: 500 }}>Purchase Requests</a>
            <a href="/family" style={{ color: 'white', textDecoration: 'none', fontWeight: 500 }}>Family Members</a>
          </nav>
        </header>
        <div style={{ maxWidth: '1200px', margin: '2rem auto', padding: '0 1.5rem' }}>
          {children}
        </div>
      </body>
    </html>
  );
}
