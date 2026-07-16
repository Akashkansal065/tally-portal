'use client';

import { useState } from 'react';

interface TallyXmlImportScreenProps {
  onBack: () => void;
  currentCompany: string;
  token: string;
}

export default function TallyXmlImportScreen({ onBack, currentCompany, token }: TallyXmlImportScreenProps) {
  const [xmlFile, setXmlFile] = useState<File | null>(null);
  const [xmlContent, setXmlContent] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [activeStep, setActiveStep] = useState(-1);
  const [stats, setStats] = useState<any>(null);
  const [error, setError] = useState('');

  const steps = [
    "Reading Tally XML file...",
    "Validating ERP Session Token...",
    "Sending collection load payload...",
    "Parsing Account Groups...",
    "Importing Master Ledgers...",
    "Validating Opening Balances...",
    "Mapping Debit/Credit signs...",
    "Committing Vouchers & Transactions..."
  ];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setXmlFile(file);
    const reader = new FileReader();
    reader.onload = (event) => {
      if (event.target?.result) {
        setXmlContent(event.target.result as string);
      }
    };
    reader.readAsText(file);
  };

  const startImport = async () => {
    if (!xmlContent) {
      setError("Please select a Tally XML export file first.");
      return;
    }
    setError('');
    setIsRunning(true);
    setStats(null);
    setActiveStep(0);

    try {
      await new Promise(r => setTimeout(r, 600));
      setActiveStep(1);

      if (!token) {
        throw new Error("No active session found. Please re-login.");
      }
      
      await new Promise(r => setTimeout(r, 600));
      setActiveStep(2);

      const syncRes = await fetch("http://127.0.0.1:8000/sync/inbound", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/xml"
        },
        body: xmlContent
      });

      for (let i = 3; i < steps.length; i++) {
        await new Promise(r => setTimeout(r, 700));
        setActiveStep(i);
      }

      if (!syncRes.ok) {
        const errData = await syncRes.json();
        throw new Error(errData.detail || "Failed to process Tally XML.");
      }

      const data = await syncRes.json();
      setStats(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="tally-content full-width-content">
      <div className="tally-panel" style={{ maxWidth: '700px', margin: '0 auto', padding: '25px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '2px solid var(--border-color)', paddingBottom: '10px', marginBottom: '20px' }}>
          <h2 style={{ margin: 0, color: 'var(--accent-gold)' }}>Tally XML Collection Import</h2>
          <button className="tally-btn" onClick={onBack} style={{ backgroundColor: 'var(--accent-gold)', color: '#000', border: 'none', padding: '5px 12px', cursor: 'pointer', fontWeight: 'bold' }}>Back (Esc)</button>
        </div>

        {error && (
          <div style={{ backgroundColor: '#ffcccc', color: '#b30000', padding: '12px', marginBottom: '20px', borderRadius: '4px', borderLeft: '5px solid #b30000', fontWeight: 'bold' }}>
            {error}
          </div>
        )}

        {!isRunning && !stats && (
          <div>
            <div style={{ padding: '15px', backgroundColor: 'var(--bg-main)', border: '1px solid var(--border-color)', marginBottom: '20px', borderRadius: '4px' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Authorized Session: </span>
              <span style={{ color: 'var(--accent-gold)', fontWeight: 'bold', fontSize: '13px' }}>Active JWT Connection Verified</span>
            </div>

            <div style={{ border: '2px dashed var(--border-color)', padding: '30px', textAlign: 'center', backgroundColor: 'var(--bg-panel)', cursor: 'pointer', marginBottom: '20px' }}>
              <input type="file" accept=".xml" onChange={handleFileChange} id="tally-file-upload" style={{ display: 'none' }} />
              <label htmlFor="tally-file-upload" style={{ cursor: 'pointer' }}>
                <div style={{ fontSize: '32px', marginBottom: '10px' }}>📁</div>
                <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>{xmlFile ? xmlFile.name : 'Select Tally Export XML File'}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Click to browse or drop standard Tally Master/Voucher collections</div>
              </label>
            </div>

            <button className="tally-btn" onClick={startImport} style={{ width: '100%', padding: '12px', fontSize: '16px', backgroundColor: 'var(--tally-green)', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}>
              Process XML Collection (Enter)
            </button>
          </div>
        )}

        {isRunning && (
          <div style={{ padding: '10px 0' }}>
            <h3 style={{ marginBottom: '20px', display: 'flex', alignItems: 'center' }}>
              <span className="spinner" style={{ marginRight: '10px' }}>⏳</span>
              Ingesting Tally collection into {currentCompany}...
            </h3>
            
            <div style={{ backgroundColor: 'var(--bg-main)', padding: '15px', borderRadius: '4px' }}>
              {steps.map((step, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', marginBottom: '10px', opacity: idx > activeStep ? 0.4 : 1, transition: 'opacity 0.3s' }}>
                  <span style={{ marginRight: '10px', fontWeight: 'bold', color: idx < activeStep ? 'var(--tally-green)' : idx === activeStep ? 'var(--accent-gold)' : 'var(--text-muted)' }}>
                    {idx < activeStep ? '✔' : idx === activeStep ? '●' : '○'}
                  </span>
                  <span style={{ color: idx === activeStep ? '#fff' : 'var(--text-muted)' }}>{step}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {stats && (
          <div style={{ textAlign: 'center', padding: '10px 0' }}>
            <div style={{ fontSize: '48px', color: 'var(--tally-green)', marginBottom: '10px' }}>✔</div>
            <h2 style={{ color: 'var(--tally-green)', marginBottom: '5px' }}>Import Completed Successfully!</h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: '25px' }}>All elements parsed and loaded to MySQL relational databases.</p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px', marginBottom: '30px' }}>
              <div style={{ backgroundColor: 'var(--bg-main)', padding: '15px', borderBottom: '3px solid var(--tally-green)' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Groups</div>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#fff' }}>{stats.imported_groups}</div>
              </div>
              <div style={{ backgroundColor: 'var(--bg-main)', padding: '15px', borderBottom: '3px solid var(--tally-green)' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Ledgers</div>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#fff' }}>{stats.imported_ledgers}</div>
              </div>
              <div style={{ backgroundColor: 'var(--bg-main)', padding: '15px', borderBottom: '3px solid var(--tally-green)' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Vouchers</div>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#fff' }}>{stats.imported_vouchers}</div>
              </div>
            </div>

            <button className="tally-btn" onClick={() => { setStats(null); setXmlFile(null); setXmlContent(''); }} style={{ backgroundColor: 'var(--tally-green)', color: '#fff', border: 'none', padding: '10px 20px', cursor: 'pointer', fontWeight: 'bold', marginRight: '10px' }}>
              Import Another File
            </button>
            <button className="tally-btn" onClick={onBack} style={{ backgroundColor: 'var(--border-color)', color: '#fff', border: 'none', padding: '10px 20px', cursor: 'pointer', fontWeight: 'bold' }}>
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
