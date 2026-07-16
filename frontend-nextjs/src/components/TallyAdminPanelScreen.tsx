'use client';

import { useState, useEffect } from 'react';
import { User, Role, Module, Permission } from '@/types';

interface TallyAdminPanelScreenProps {
  onBack: () => void;
  token: string;
}

export default function TallyAdminPanelScreen({ onBack, token }: TallyAdminPanelScreenProps) {
  const [activeTab, setActiveTab] = useState<'users' | 'permissions'>('users');
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [modules, setModules] = useState<Module[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<number>(2); 
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const [newUsername, setNewUsername] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRoleId, setNewRoleId] = useState(2);

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const usersRes = await fetch("http://127.0.0.1:8000/admin/users", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (usersRes.ok) setUsers(await usersRes.json());

      const rolesRes = await fetch("http://127.0.0.1:8000/admin/roles", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (rolesRes.ok) {
        const rolesData = await rolesRes.json();
        setRoles(rolesData);
      }

      const modulesRes = await fetch("http://127.0.0.1:8000/admin/modules", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (modulesRes.ok) setModules(await modulesRes.json());

      const permsRes = await fetch("http://127.0.0.1:8000/admin/permissions", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (permsRes.ok) setPermissions(await permsRes.json());

    } catch (err) {
      setError("Failed to load administration data from backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [token]);

  const handleCreateUser = async () => {
    setError('');
    setSuccessMsg('');
    if (!newUsername.trim() || !newEmail.trim() || !newPassword.trim()) {
      setError("All fields are required to create a new user.");
      return;
    }
    try {
      const res = await fetch("http://127.0.0.1:8000/admin/users", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          username: newUsername.trim(),
          email: newEmail.trim(),
          password: newPassword,
          role_id: newRoleId
        })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to create new user.");
      }
      setSuccessMsg(`User ${newUsername} successfully created!`);
      setNewUsername('');
      setNewEmail('');
      setNewPassword('');
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRoleChange = async (userId: number, roleId: string) => {
    setError('');
    setSuccessMsg('');
    try {
      const res = await fetch(`http://127.0.0.1:8000/admin/users/${userId}/role`, {
        method: "PUT",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ role_id: parseInt(roleId) })
      });
      if (!res.ok) throw new Error("Failed to update user role.");
      setSuccessMsg("User role updated successfully!");
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handlePermissionToggle = (moduleId: number, field: 'can_read' | 'can_create' | 'can_update' | 'can_delete') => {
    setPermissions(prev => {
      const index = prev.findIndex(p => p.role_id === selectedRoleId && p.module_id === moduleId);
      if (index > -1) {
        const updated = [...prev];
        updated[index] = { ...updated[index], [field]: !updated[index][field] };
        return updated;
      } else {
        return [...prev, {
          permission_id: 0,
          role_id: selectedRoleId,
          module_id: moduleId,
          can_create: field === 'can_create',
          can_read: field === 'can_read',
          can_update: field === 'can_update',
          can_delete: field === 'can_delete'
        } as Permission];
      }
    });
  };

  const handleSavePermissions = async () => {
    setError('');
    setSuccessMsg('');
    const payload = permissions
      .filter(p => p.role_id === selectedRoleId)
      .map(p => ({
        role_id: p.role_id,
        module_id: p.module_id,
        can_create: !!p.can_create,
        can_read: !!p.can_read,
        can_update: !!p.can_update,
        can_delete: !!p.can_delete
      }));

    try {
      const res = await fetch("http://127.0.0.1:8000/admin/permissions", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Failed to save permissions matrix.");
      setSuccessMsg("Permissions saved successfully!");
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="tally-content full-width-content">
      <div className="tally-panel" style={{ maxWidth: '850px', margin: '0 auto', padding: '25px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '2px solid var(--border-color)', paddingBottom: '10px', marginBottom: '20px' }}>
          <h2 style={{ margin: 0, color: 'var(--accent-gold)' }}>Administration & User Control Panel</h2>
          <button className="tally-btn" onClick={onBack} style={{ backgroundColor: 'var(--accent-gold)', color: '#000', border: 'none', padding: '5px 12px', cursor: 'pointer', fontWeight: 'bold' }}>Back (Esc)</button>
        </div>

        {error && (
          <div style={{ backgroundColor: '#ffcccc', color: '#b30000', padding: '10px', marginBottom: '15px', borderRadius: '4px', borderLeft: '5px solid #b30000', fontWeight: 'bold' }}>
            ⚠️ {error}
          </div>
        )}

        {successMsg && (
          <div style={{ backgroundColor: '#ccffcc', color: '#006600', padding: '10px', marginBottom: '15px', borderRadius: '4px', borderLeft: '5px solid #006600', fontWeight: 'bold' }}>
            ✔ {successMsg}
          </div>
        )}

        <div style={{ display: 'flex', gap: '5px', marginBottom: '20px', borderBottom: '1px solid var(--border-color)' }}>
          <button 
            onClick={() => setActiveTab('users')} 
            style={{
              padding: '10px 20px',
              backgroundColor: activeTab === 'users' ? 'var(--bg-dark)' : 'transparent',
              color: activeTab === 'users' ? 'var(--accent-gold)' : 'var(--text-muted)',
              border: activeTab === 'users' ? '1px solid var(--border-color)' : 'none',
              borderBottom: 'none',
              cursor: 'pointer',
              fontWeight: 'bold'
            }}
          >
            User Roles
          </button>
          <button 
            onClick={() => setActiveTab('permissions')} 
            style={{
              padding: '10px 20px',
              backgroundColor: activeTab === 'permissions' ? 'var(--bg-dark)' : 'transparent',
              color: activeTab === 'permissions' ? 'var(--accent-gold)' : 'var(--text-muted)',
              border: activeTab === 'permissions' ? '1px solid var(--border-color)' : 'none',
              borderBottom: 'none',
              cursor: 'pointer',
              fontWeight: 'bold'
            }}
          >
            Role Permissions Matrix
          </button>
        </div>

        {loading && <div style={{ color: 'var(--accent-gold)', textAlign: 'center', padding: '20px' }}>Loading...</div>}

        {!loading && activeTab === 'users' && (
          <div>
            <div style={{ border: '1px solid var(--border-color)', padding: '15px', marginBottom: '20px', backgroundColor: 'var(--bg-dark)' }}>
              <h4 style={{ margin: '0 0 15px 0', color: 'var(--accent-gold)', textTransform: 'uppercase', fontSize: '12px', letterSpacing: '0.5px' }}>Create New System User</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '15px', alignItems: 'flex-end' }}>
                <div style={{ flex: 1, minWidth: '150px' }}>
                  <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '5px' }}>Username</label>
                  <input 
                    type="text" 
                    value={newUsername} 
                    onChange={(e) => setNewUsername(e.target.value)}
                    placeholder="e.g. jdoe"
                    style={{ width: '100%', padding: '6px 10px', backgroundColor: 'var(--bg-main)', border: '1px solid var(--border-color)', color: '#fff', outline: 'none' }}
                  />
                </div>
                <div style={{ flex: 1, minWidth: '150px' }}>
                  <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '5px' }}>Email Address</label>
                  <input 
                    type="email" 
                    value={newEmail} 
                    onChange={(e) => setNewEmail(e.target.value)}
                    placeholder="e.g. john@company.com"
                    style={{ width: '100%', padding: '6px 10px', backgroundColor: 'var(--bg-main)', border: '1px solid var(--border-color)', color: '#fff', outline: 'none' }}
                  />
                </div>
                <div style={{ flex: 1, minWidth: '150px' }}>
                  <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '5px' }}>Password</label>
                  <input 
                    type="password" 
                    value={newPassword} 
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Password..."
                    style={{ width: '100%', padding: '6px 10px', backgroundColor: 'var(--bg-main)', border: '1px solid var(--border-color)', color: '#fff', outline: 'none' }}
                  />
                </div>
                <div style={{ flex: 1, minWidth: '150px' }}>
                  <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '5px' }}>Assigned Role</label>
                  <select 
                    value={newRoleId} 
                    onChange={(e) => setNewRoleId(parseInt(e.target.value))}
                    style={{ width: '100%', padding: '6px 10px', backgroundColor: 'var(--bg-main)', border: '1px solid var(--border-color)', color: '#fff', outline: 'none' }}
                  >
                    {roles.map(r => (
                      <option key={r.role_id} value={r.role_id}>{r.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <button 
                    onClick={handleCreateUser}
                    className="tally-btn" 
                    style={{ backgroundColor: 'var(--tally-green)', color: '#fff', border: 'none', padding: '8px 15px', cursor: 'pointer', fontWeight: 'bold' }}
                  >
                    Add User (Enter)
                  </button>
                </div>
              </div>
            </div>

            <table className="report-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Status</th>
                  <th>Active Role</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.user_id}>
                    <td>{u.username}</td>
                    <td>{u.email}</td>
                    <td style={{ color: u.is_active ? 'var(--tally-green)' : 'red' }}>{u.is_active ? 'Active' : 'Inactive'}</td>
                    <td>
                      <select 
                        value={u.role_id} 
                        onChange={(e) => handleRoleChange(u.user_id, e.target.value)}
                        style={{
                          padding: '5px',
                          backgroundColor: 'var(--bg-main)',
                          color: '#fff',
                          border: '1px solid var(--border-color)'
                        }}
                      >
                        {roles.map(r => (
                          <option key={r.role_id} value={r.role_id}>{r.name} - {r.description}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && activeTab === 'permissions' && (
          <div>
            <div style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '15px' }}>
              <label style={{ fontWeight: 'bold', color: 'var(--text-muted)' }}>Configure Target Role:</label>
              <select 
                value={selectedRoleId} 
                onChange={(e) => setSelectedRoleId(parseInt(e.target.value))}
                style={{
                  padding: '8px 12px',
                  backgroundColor: 'var(--bg-main)',
                  color: '#fff',
                  border: '1px solid var(--border-color)',
                  fontSize: '14px'
                }}
              >
                {roles.filter(r => r.name !== 'Admin').map(r => (
                  <option key={r.role_id} value={r.role_id}>{r.name} ({r.description})</option>
                ))}
              </select>
            </div>

            <table className="report-table">
              <thead>
                <tr>
                  <th>System Module</th>
                  <th className="text-center">Read (GET)</th>
                  <th className="text-center">Create (POST)</th>
                  <th className="text-center">Update (PUT)</th>
                  <th className="text-center">Delete (DELETE)</th>
                </tr>
              </thead>
              <tbody>
                {modules.map(mod => {
                  const perm = permissions.find(p => p.role_id === selectedRoleId && p.module_id === mod.module_id) || {
                    can_read: false,
                    can_create: false,
                    can_update: false,
                    can_delete: false
                  };
                  return (
                    <tr key={mod.module_id}>
                      <td style={{ fontWeight: 'bold' }}>
                        {mod.name} 
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 'normal' }}>Code: {mod.code}</div>
                      </td>
                      <td className="text-center">
                        <input 
                          type="checkbox" 
                          checked={!!perm.can_read} 
                          onChange={() => handlePermissionToggle(mod.module_id, 'can_read')}
                        />
                      </td>
                      <td className="text-center">
                        <input 
                          type="checkbox" 
                          checked={!!perm.can_create} 
                          onChange={() => handlePermissionToggle(mod.module_id, 'can_create')}
                        />
                      </td>
                      <td className="text-center">
                        <input 
                          type="checkbox" 
                          checked={!!perm.can_update} 
                          onChange={() => handlePermissionToggle(mod.module_id, 'can_update')}
                        />
                      </td>
                      <td className="text-center">
                        <input 
                          type="checkbox" 
                          checked={!!perm.can_delete} 
                          onChange={() => handlePermissionToggle(mod.module_id, 'can_delete')}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <div style={{ marginTop: '20px', textAlign: 'right' }}>
              <button className="tally-btn" onClick={handleSavePermissions} style={{ backgroundColor: 'var(--tally-green)', color: '#fff', border: 'none', padding: '10px 20px', cursor: 'pointer', fontWeight: 'bold' }}>
                Save Permissions Matrix (Enter)
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
