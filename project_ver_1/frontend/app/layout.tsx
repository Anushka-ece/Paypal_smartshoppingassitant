import React from 'react';
import './globals.css';

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
        <header className="site-header">
          <div className="site-brand">
            <span className="site-brand-name">PayPal</span>
            <span className="site-brand-label">Family Budget &amp; Guardrails</span>
          </div>
          <nav className="site-nav">
            <a href="/dashboard">Dashboard</a>
            <a href="/budgets">Envelopes &amp; Budgets</a>
            <a href="/transactions">Transactions &amp; Refunds</a>
            <a href="/guardrails">AI Guardrails</a>
            <a href="/guardrails/simulator">Rule Simulator</a>
            <a href="/requests">Purchase Requests</a>
            <a href="/family">Family Members</a>
            <a href="/login">Sign in</a>
          </nav>
        </header>
        <div style={{ maxWidth: '1200px', margin: '2rem auto', padding: '0 1.5rem' }}>
          {children}
        </div>
      </body>
    </html>
  );
}
