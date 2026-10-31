'use client';

import React, { useState } from 'react';

interface Member {
  id: number;
  name: string;
  email: string;
  role: 'PARENT' | 'CO_PARENT' | 'CHILD';
  age?: number;
  allowanceStatus: string;
}

export default function FamilyPage() {
  const [members, setMembers] = useState<Member[]>([
    { id: 1, name: 'Homer Simpson', email: 'homer@example.com', role: 'PARENT', allowanceStatus: 'Master Payer' },
    { id: 2, name: 'Marge Simpson', email: 'marge@example.com', role: 'CO_PARENT', allowanceStatus: 'Co-Guardian' },
    { id: 3, name: 'Bart Simpson', email: 'bart@example.com', role: 'CHILD', age: 10, allowanceStatus: '$15.00 / week' },
    { id: 4, name: 'Lisa Simpson', email: 'lisa@example.com', role: 'CHILD', age: 8, allowanceStatus: '$15.00 / week' },
  ]);

  const [inviteName, setInviteName] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'CO_PARENT' | 'CHILD'>('CHILD');
  const [generatedLink, setGeneratedLink] = useState<string | null>(null);

  const handleGenerateInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    const token = `inv-${Math.random().toString(36).substring(2, 10)}`;
    const link = `https://familybudget.paypal.com/invite?token=${token}&role=${inviteRole}`;
    setGeneratedLink(link);
    setInviteName('');
    setInviteEmail('');
  };

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.8rem', margin: '0 0 0.25rem 0', color: '#003087' }}>Family Members & Permissions</h2>
        <p style={{ margin: 0, color: '#64748b', fontSize: '0.95rem' }}>
          Manage parental oversight roles, child account links, and COPPA verifiable consent tokens.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '2rem' }}>
        {/* Family Members List */}
        <div>
          <h3 style={{ fontSize: '1.2rem', color: '#003087', marginBottom: '1rem' }}>Active Family Members</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {members.map((m) => (
              <div
                key={m.id}
                style={{
                  background: 'white',
                  padding: '1.25rem',
                  borderRadius: '0.5rem',
                  border: '1px solid #e2e8f0',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: '1.05rem' }}>{m.name}</div>
                  <div style={{ color: '#64748b', fontSize: '0.85rem' }}>{m.email}</div>
                  {m.age && <div style={{ fontSize: '0.8rem', color: '#475569' }}>Age: {m.age} (COPPA Monitored)</div>}
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span
                    style={{
                      background: m.role === 'PARENT' ? '#dbeafe' : m.role === 'CO_PARENT' ? '#f3e8ff' : '#dcfce7',
                      color: m.role === 'PARENT' ? '#1e40af' : m.role === 'CO_PARENT' ? '#6b21a8' : '#15803d',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      padding: '0.2rem 0.5rem',
                      borderRadius: '0.25rem',
                    }}
                  >
                    {m.role}
                  </span>
                  <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.35rem' }}>{m.allowanceStatus}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Invite Member Card */}
        <div style={{ background: 'white', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #e2e8f0' }}>
          <h3 style={{ fontSize: '1.2rem', color: '#003087', margin: '0 0 1rem 0' }}>Invite Co-Parent or Child</h3>
          <form onSubmit={handleGenerateInvite} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                Full Name:
              </label>
              <input
                type="text"
                value={inviteName}
                onChange={(e) => setInviteName(e.target.value)}
                placeholder="e.g. Maggie Simpson"
                style={{ width: '100%', padding: '0.5rem', borderRadius: '0.375rem', border: '1px solid #cbd5e1', fontSize: '0.9rem', boxSizing: 'border-box' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                Email Address:
              </label>
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="e.g. maggie@example.com"
                style={{ width: '100%', padding: '0.5rem', borderRadius: '0.375rem', border: '1px solid #cbd5e1', fontSize: '0.9rem', boxSizing: 'border-box' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                Role:
              </label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as 'CO_PARENT' | 'CHILD')}
                style={{ width: '100%', padding: '0.5rem', borderRadius: '0.375rem', border: '1px solid #cbd5e1', fontSize: '0.9rem', boxSizing: 'border-box' }}
              >
                <option value="CHILD">Child / Teen (Pocket Money & Allowance)</option>
                <option value="CO_PARENT">Co-Parent (Approval Permissions)</option>
              </select>
            </div>

            <button
              type="submit"
              style={{
                background: '#003087',
                color: 'white',
                border: 'none',
                padding: '0.75rem',
                borderRadius: '0.375rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Generate Expiring Invite Link
            </button>
          </form>

          {generatedLink && (
            <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#f8fafc', borderRadius: '0.375rem', border: '1px solid #cbd5e1' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#15803d', marginBottom: '0.25rem' }}>
                ✅ Secure Invite Link Generated:
              </div>
              <input
                readOnly
                value={generatedLink}
                style={{ width: '100%', padding: '0.5rem', fontSize: '0.8rem', borderRadius: '0.25rem', border: '1px solid #e2e8f0', background: 'white', boxSizing: 'border-box' }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
