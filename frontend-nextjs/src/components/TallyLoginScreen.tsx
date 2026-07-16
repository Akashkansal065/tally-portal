'use client';

import { useState } from 'react';

interface TallyLoginScreenProps {
  onLoginSuccess: (token: string, email: string) => void;
}

export default function TallyLoginScreen({ onLoginSuccess }: TallyLoginScreenProps) {
  const [email, setEmail] = useState('admin_test@test.com');
  const [password, setPassword] = useState('securepassword123');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      if (!res.ok) {
        throw new Error("Invalid email or password.");
      }
      const data = await res.json();
      onLoginSuccess(data.access_token, email);
    } catch (err: any) {
      setError(err.message || "Failed to connect to ERP server.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      backgroundColor: '#0c181b', // fallback variable background
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      color: '#fff',
      fontFamily: "'Courier New', Courier, monospace"
    }}>
      <div className="tally-panel" style={{
        width: '450px',
        border: '3px double var(--accent-gold)',
        padding: '30px',
        boxShadow: '0 0 20px rgba(0,0,0,0.8)',
        backgroundColor: 'var(--bg-main)'
      }}>
        <div style={{ textAlign: 'center', marginBottom: '25px' }}>
          <h1 style={{ color: 'var(--tally-green)', margin: '0 0 5px 0', fontSize: '28px', fontWeight: 'bold' }}>MyTally Prime</h1>
          <div style={{ color: 'var(--accent-gold)', fontSize: '12px', letterSpacing: '2px', textTransform: 'uppercase' }}>Web ERP Gateway</div>
        </div>

        {error && (
          <div style={{
            backgroundColor: 'rgba(255, 0, 0, 0.15)',
            color: '#ff6b6b',
            padding: '10px',
            border: '1px solid #ff4d4d',
            marginBottom: '20px',
            fontSize: '13px',
            textAlign: 'center'
          }}>
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', color: 'var(--text-muted)' }}>Email Address</label>
            <input 
              type="email" 
              value={email} 
              onChange={e => setEmail(e.target.value)} 
              required
              style={{
                width: '100%',
                padding: '10px',
                backgroundColor: 'var(--bg-main)',
                border: '1px solid var(--border-color)',
                color: '#fff',
                outline: 'none'
              }}
            />
          </div>

          <div style={{ marginBottom: '25px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', color: 'var(--text-muted)' }}>Security Password</label>
            <input 
              type="password" 
              value={password} 
              onChange={e => setPassword(e.target.value)} 
              required
              style={{
                width: '100%',
                padding: '10px',
                backgroundColor: 'var(--bg-main)',
                border: '1px solid var(--border-color)',
                color: '#fff',
                outline: 'none'
              }}
            />
          </div>

          <button 
            type="submit" 
            disabled={loading}
            className="tally-btn" 
            style={{
              width: '100%',
              padding: '12px',
              backgroundColor: 'var(--tally-green)',
              color: '#fff',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '15px',
              textTransform: 'uppercase'
            }}
          >
            {loading ? 'Authenticating...' : 'Secure Login (Enter)'}
          </button>
        </form>

        <div style={{ marginTop: '20px', textAlign: 'center', fontSize: '11px', color: 'var(--text-muted)' }}>
          System seeded with default admin: <br/>
          <span style={{ color: 'var(--accent-gold)' }}>admin_test@test.com</span> / <span style={{ color: 'var(--accent-gold)' }}>securepassword123</span>
        </div>
      </div>
    </div>
  );
}
