'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'
import { Search, Plus, Edit2, Trash2, ChevronRight, ChevronDown, FolderTree, RefreshCw, Info, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import GroupFormModal, { AccountGroupTreeNode, GroupFormData } from '@/components/GroupFormModal'

export default function GroupsPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()

  const [groups, setGroups] = useState<AccountGroupTreeNode[]>([])
  const [loading, setLoading] = useState(true)
  
  // Modals
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editGroupData, setEditGroupData] = useState<GroupFormData | null>(null)
  const [parentGroupId, setParentGroupId] = useState<number | null>(null)

  // Tree state
  const [expandedNodes, setExpandedNodes] = useState<Set<number>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showLedger) { router.replace('/'); return }
    fetchData()
  }, [user, token])

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/ledgers/groups/tree`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setGroups(Array.isArray(data) ? data : [])
        // Expand top level by default
        const topLevelIds = new Set<number>(data.map((g: any) => Number(g.group_id)))
        setExpandedNodes(topLevelIds)
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleOpenCreateModal = (parentId: number | null = null) => {
    setEditGroupData(null)
    setParentGroupId(parentId)
    setIsFormOpen(true)
  }

  const handleOpenEditModal = (group: any, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditGroupData({
      group_id: group.group_id,
      name: group.name,
      parent_group_id: group.parent_group_id,
      nature: group.nature,
      alias_name: group.alias_name,
      is_addable: group.is_addable,
      is_revenue: group.is_revenue,
      is_deemed_positive: group.is_deemed_positive,
      affects_gross_profit: group.affects_gross_profit,
      is_subledger: group.is_subledger || false,
      is_billwise_on: group.is_billwise_on || false,
      used_for_calculation: group.used_for_calculation || false,
      method_to_allocate: group.method_to_allocate || 'Not Applicable',
      sort_position: group.sort_position || 1000,
      language_id: group.language_id || 1033,
      gst_details: group.gst_details || []
    })
    setIsFormOpen(true)
  }

  const handleDelete = async (group: any, e: React.MouseEvent) => {
    e.stopPropagation()
    if (group.is_system_defined) {
      alert("System defined groups cannot be deleted.")
      return
    }
    if (!confirm(`Are you sure you want to delete the group "${group.name}"?`)) return

    try {
      const res = await fetch(`${API_BASE}/ledgers/groups/${group.group_id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to delete')
      }
      fetchData()
    } catch (err: any) {
      alert(err.message)
    }
  }

  const toggleNode = (groupId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    const next = new Set(expandedNodes)
    if (next.has(groupId)) {
      next.delete(groupId)
    } else {
      next.add(groupId)
    }
    setExpandedNodes(next)
  }

  const renderTree = (nodes: AccountGroupTreeNode[], level = 0) => {
    return nodes.map((node) => {
      const isExpanded = expandedNodes.has(node.group_id)
      const hasChildren = node.children && node.children.length > 0
      
      const matchesSearch = searchQuery && node.name.toLowerCase().includes(searchQuery.toLowerCase())

      return (
        <div key={node.group_id} className="w-full">
          <div 
            className={cn(
              "group flex items-center justify-between p-3 border-b border-border hover:bg-muted/50 transition-colors cursor-pointer",
              matchesSearch && "bg-emerald-500/10"
            )}
            onClick={(e) => hasChildren && toggleNode(node.group_id, e)}
            style={{ paddingLeft: `${level * 2 + 1}rem` }}
          >
            <div className="flex items-center gap-3">
              <div 
                className={cn(
                  "w-5 h-5 flex items-center justify-center rounded transition-colors",
                  hasChildren ? "hover:bg-muted" : "opacity-0"
                )}
              >
                {hasChildren && (
                  isExpanded ? <ChevronDown className="w-4 h-4 text-muted-foreground" /> : <ChevronRight className="w-4 h-4 text-muted-foreground" />
                )}
              </div>
              <div className="flex flex-col">
                <span className={cn(
                  "font-medium",
                  level === 0 ? "text-foreground text-base" : "text-foreground/80 text-sm",
                  matchesSearch && "text-emerald-600 font-bold"
                )}>
                  {node.name}
                </span>
                {node.alias_name && (
                  <span className="text-xs text-muted-foreground">{node.alias_name}</span>
                )}
              </div>
              
              <div className="ml-3 px-2 py-0.5 rounded-full bg-muted border border-border/40 text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                {node.nature}
              </div>
              
              {(node as any).is_system_defined && (
                <div className="ml-1 px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 text-[10px] font-bold uppercase tracking-wider">
                  System
                </div>
              )}
            </div>

            <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={(e) => { e.stopPropagation(); handleOpenCreateModal(node.group_id) }}
                className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
                title="Add Sub-Group"
              >
                <Plus className="w-4 h-4" />
              </button>
              <button
                onClick={(e) => handleOpenEditModal(node, e)}
                className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
                title="Edit Group"
              >
                <Edit2 className="w-4 h-4" />
              </button>
              {!(node as any).is_system_defined && (
                <button
                  onClick={(e) => handleDelete(node, e)}
                  className="p-1.5 text-red-500/70 hover:text-red-600 hover:bg-red-500/10 rounded-lg transition-colors"
                  title="Delete Group"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
          
          {hasChildren && isExpanded && (
            <div className="flex flex-col w-full animate-in slide-in-from-top-2 duration-200">
              {renderTree(node.children!, level + 1)}
            </div>
          )}
        </div>
      )
    })
  }

  useEffect(() => {
    if (searchQuery.trim().length > 0) {
      const allIds = new Set<number>()
      const traverse = (nodes: AccountGroupTreeNode[]) => {
        nodes.forEach(n => {
          allIds.add(n.group_id)
          if (n.children) traverse(n.children)
        })
      }
      traverse(groups)
      setExpandedNodes(allIds)
    } else {
      const topLevelIds = new Set(groups.map((g: any) => g.group_id))
      setExpandedNodes(topLevelIds)
    }
  }, [searchQuery, groups])

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      
      {/* Header bar */}
      <div className="px-4 py-3 bg-card border-b border-border flex items-center justify-between shadow-xs">
        <div>
          <h1 className="text-base font-black text-foreground tracking-tight">Group Master</h1>
          <p className="text-[11px] text-muted-foreground font-semibold">Manage chart of accounts hierarchy</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-2 border border-border bg-background hover:bg-muted text-foreground rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            title="Refresh Groups"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin text-emerald-600")} />
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
          
          <button
            onClick={() => handleOpenCreateModal(null)}
            className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-extrabold shadow-sm transition-all flex items-center gap-1.5 cursor-pointer active:scale-95"
          >
            <Plus className="w-4 h-4" />
            + New Primary Group
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pt-4 pb-6 max-w-4xl mx-auto w-full space-y-4">
        {/* Search */}
        <div className="bg-card border border-border rounded-xl p-2 shadow-sm">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input 
              type="text"
              placeholder="Search groups..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-background border border-border rounded-lg pl-9 pr-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:ring-1 focus:ring-emerald-500 transition-all outline-none"
            />
          </div>
        </div>

        {/* Tree List */}
        <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20">
              <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin mb-4" />
              <p className="text-muted-foreground text-sm font-medium">Loading hierarchy...</p>
            </div>
          ) : groups.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center px-4">
              <FolderTree className="w-12 h-12 text-muted-foreground/50 mb-4" />
              <h3 className="text-lg font-bold text-foreground mb-1">No Groups Found</h3>
              <p className="text-muted-foreground text-sm max-w-md">
                Get started by creating your first primary group.
              </p>
            </div>
          ) : (
            <div className="flex flex-col w-full text-sm">
              {renderTree(groups)}
            </div>
          )}
        </div>
      </div>

      <GroupFormModal
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        onSuccess={fetchData}
        initialData={editGroupData}
        token={token}
        parentGroupId={parentGroupId}
      />
    </div>
  )
}
