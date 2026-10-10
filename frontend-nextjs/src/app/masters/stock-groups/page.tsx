'use client'

import React, { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, cn } from '@/lib/utils'
import { 
  Plus, 
  Edit2, 
  Trash2, 
  X, 
  ChevronRight, 
  Folder, 
  FolderOpen, 
  FolderTree, 
  Search, 
  Layers
} from 'lucide-react'
import DeleteGroupModal from '@/components/DeleteGroupModal'

type StockGroupAlias = {
  alias: string
}

type StockGroup = {
  stock_group_id: number
  name: string
  parent_id: number | null
  is_active: boolean
  aliases: StockGroupAlias[]
}

// Tree node type
type TreeNode = StockGroup & {
  children: TreeNode[]
  isExpanded?: boolean
}

export default function StockGroupsPage() {
  const { user, token, can } = useAuth()
  const router = useRouter()
  
  const [groups, setGroups] = useState<StockGroup[]>([])
  const [loading, setLoading] = useState(true)

  // Tree state
  const [expandedNodes, setExpandedNodes] = useState<Set<number>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')

  // Edit Panel state
  const [isPanelOpen, setIsPanelOpen] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [groupId, setGroupId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [parentId, setParentId] = useState<number | ''>('')
  const [isActive, setIsActive] = useState(true)
  const [aliases, setAliases] = useState<string>('')
  const [groupToDelete, setGroupToDelete] = useState<{ group_id: number; name: string } | null>(null)

  const fetchGroups = async () => {
    try {
      const res = await fetch(`${API_BASE}/inventory/groups`, { headers: authHeaders(token) })
      const data = await res.json()
      setGroups(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!can('stock_groups', 'read')) { router.replace('/'); return }
    fetchGroups()
  }, [user, can, router])

  // Build tree
  const tree = useMemo(() => {
    const map = new Map<number, TreeNode>()
    const roots: TreeNode[] = []

    // Initialize map
    groups.forEach(g => {
      map.set(g.stock_group_id, { ...g, children: [] })
    })

    // Build hierarchy
    groups.forEach(g => {
      if (g.parent_id && map.has(g.parent_id)) {
        map.get(g.parent_id)!.children.push(map.get(g.stock_group_id)!)
      } else {
        roots.push(map.get(g.stock_group_id)!)
      }
    })

    return roots
  }, [groups])

  // Auto-expand on search
  useEffect(() => {
    if (searchQuery.trim()) {
      const allWithChildren = new Set<number>()
      groups.forEach(g => {
        if (groups.some(c => c.parent_id === g.stock_group_id)) {
          allWithChildren.add(g.stock_group_id)
        }
      })
      setExpandedNodes(allWithChildren)
    }
  }, [searchQuery, groups])

  // Filter tree by search query
  const filteredTree = useMemo(() => {
    if (!searchQuery.trim()) return tree

    const q = searchQuery.toLowerCase().trim()

    const filterNodes = (nodes: TreeNode[]): TreeNode[] => {
      const result: TreeNode[] = []

      for (const node of nodes) {
        const matchesSelf = 
          node.name.toLowerCase().includes(q) ||
          (node.aliases || []).some(a => a.alias.toLowerCase().includes(q))
        
        const matchingChildren = filterNodes(node.children)

        if (matchesSelf || matchingChildren.length > 0) {
          result.push({
            ...node,
            children: matchingChildren
          })
        }
      }

      return result
    }

    return filterNodes(tree)
  }, [tree, searchQuery])

  const toggleExpand = (id: number) => {
    const next = new Set(expandedNodes)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setExpandedNodes(next)
  }

  const expandAll = () => {
    const allParentIds = new Set<number>()
    groups.forEach(g => {
      if (groups.some(c => c.parent_id === g.stock_group_id)) {
        allParentIds.add(g.stock_group_id)
      }
    })
    setExpandedNodes(allParentIds)
  }

  const collapseAll = () => {
    setExpandedNodes(new Set())
  }

  const allParentsCount = useMemo(() => {
    return groups.filter(g => groups.some(c => c.parent_id === g.stock_group_id)).length
  }, [groups])

  const isAllExpanded = allParentsCount > 0 && expandedNodes.size >= allParentsCount

  const openCreate = (prefillParentId?: number) => {
    setIsEditing(false)
    setGroupId(null)
    setName('')
    setParentId(prefillParentId || '')
    setIsActive(true)
    setAliases('')
    setIsPanelOpen(true)
  }

  const openEdit = (g: StockGroup) => {
    setIsEditing(true)
    setGroupId(g.stock_group_id)
    setName(g.name)
    setParentId(g.parent_id || '')
    setIsActive(g.is_active)
    setAliases((g.aliases || []).map(a => a.alias).join(', '))
    setIsPanelOpen(true)
  }

  const closePanel = () => {
    setIsPanelOpen(false)
    setGroupId(null)
    setIsEditing(false)
  }

  const handleDelete = (id: number) => {
    const g = groups.find(x => x.stock_group_id === id)
    setGroupToDelete({ group_id: id, name: g?.name ?? '' })
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return alert("Name is required")

    const aliasList = aliases.split(',').map(s => s.trim()).filter(s => s.length > 0)

    const payload = {
      name: name.trim(),
      parent_id: parentId === '' ? null : Number(parentId),
      is_active: isActive,
      aliases: aliasList
    }

    const url = isEditing ? `${API_BASE}/inventory/groups/${groupId}` : `${API_BASE}/inventory/groups`
    const method = isEditing ? 'PUT' : 'POST'

    try {
      const res = await fetch(url, {
        method,
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })
      const d = await res.json().catch(() => ({}))
      if (!res.ok) {
        alert(typeof d.detail === 'string' ? d.detail : d.detail?.message || "Error saving stock group")
        return
      }
      closePanel()
      fetchGroups()
      if (d.tally_synced === false && d.tally_status !== 'NOT_CONFIGURED') {
        alert(`Saved in MyTally, but not yet in Tally: ${d.tally_message || d.tally_status}. It will be sent again when Tally is reachable.`)
      }
    } catch (e) {
      console.error(e)
    }
  }

  // Recursive render
  const renderTree = (nodes: TreeNode[], depth = 0) => {
    return nodes.map(node => {
      const isExpanded = expandedNodes.has(node.stock_group_id)
      const hasChildren = node.children.length > 0
      const isSelected = isPanelOpen && groupId === node.stock_group_id

      return (
        <div key={node.stock_group_id} className="relative">
          <div 
            className={cn(
              "flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl transition-all cursor-pointer group select-none",
              isSelected
                ? "bg-primary/10 text-primary border border-primary/30 shadow-xs"
                : "hover:bg-muted/60 text-foreground border border-transparent"
            )}
            onClick={() => {
              if (hasChildren) toggleExpand(node.stock_group_id)
              else openEdit(node)
            }}
          >
            {/* Left section: expand chevron, folder icon, name, and badges */}
            <div className="flex items-center gap-2.5 min-w-0 flex-1">
              {/* Selected accent pill indicator */}
              {isSelected && (
                <span className="w-1.5 h-4 rounded-full bg-primary shrink-0 -ml-1" />
              )}

              {/* Expand/Collapse Chevron or spacer dot */}
              <div className="w-5 h-5 flex items-center justify-center shrink-0">
                {hasChildren ? (
                  <button 
                    type="button"
                    onClick={(e) => { 
                      e.stopPropagation()
                      toggleExpand(node.stock_group_id) 
                    }}
                    className="w-5 h-5 flex items-center justify-center rounded-md hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-all cursor-pointer"
                    title={isExpanded ? "Collapse subgroup" : "Expand subgroup"}
                  >
                    <ChevronRight className={cn("h-3.5 w-3.5 transition-transform duration-200", isExpanded && "rotate-90")} />
                  </button>
                ) : (
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/25" />
                )}
              </div>
              
              {/* Folder Icon */}
              {isExpanded ? (
                <FolderOpen className={cn("h-4 w-4 shrink-0", isSelected ? "text-primary" : "text-primary/80")} />
              ) : (
                <Folder className={cn("h-4 w-4 shrink-0", isSelected ? "text-primary" : "text-muted-foreground")} />
              )}
              
              {/* Group Name */}
              <span className={cn(
                "text-sm tracking-tight truncate",
                !node.is_active && "text-muted-foreground",
                isSelected ? "font-bold text-foreground" : "font-semibold"
              )}>
                {node.name}
              </span>
              
              {/* Inactive badge */}
              {!node.is_active && (
                <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border shrink-0">
                  Inactive
                </span>
              )}

              {/* Subgroups count badge */}
              {hasChildren && (
                <span className="text-[10px] font-bold text-muted-foreground bg-muted/80 px-2 py-0.5 rounded-full shrink-0">
                  {node.children.length} {node.children.length === 1 ? 'sub' : 'subs'}
                </span>
              )}

              {/* Aliases badge */}
              {node.aliases?.length > 0 && (
                <span className="text-[10px] font-semibold text-muted-foreground bg-muted/60 px-2 py-0.5 rounded-full shrink-0 hidden md:inline-flex items-center gap-1">
                  +{node.aliases.length} alias{node.aliases.length > 1 ? 'es' : ''}
                </span>
              )}

              {/* Active editing indicator */}
              {isSelected && (
                <span className="text-[9px] font-extrabold uppercase tracking-wider px-1.5 py-0.5 rounded bg-primary/20 text-primary border border-primary/30 shrink-0 ml-auto mr-1">
                  Editing
                </span>
              )}
            </div>

            {/* Right section: Action Buttons */}
            <div 
              className={cn(
                "flex items-center gap-1 shrink-0 transition-opacity",
                isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100 focus-within:opacity-100"
              )}
              onClick={(e) => e.stopPropagation()}
            >
              {can('stock_groups', 'create') && (
                <button 
                  type="button"
                  onClick={() => openCreate(node.stock_group_id)} 
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors cursor-pointer"
                  title="Add Subgroup under this group"
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              )}
              {can('stock_groups', 'update') && (
                <button 
                  type="button"
                  onClick={() => openEdit(node)} 
                  className={cn(
                    "p-1.5 rounded-lg transition-colors cursor-pointer",
                    isSelected 
                      ? "text-primary bg-primary/15 font-bold" 
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  )}
                  title="Edit Stock Group"
                >
                  <Edit2 className="h-3.5 w-3.5" />
                </button>
              )}
              {can('stock_groups', 'delete') && (
                <button 
                  type="button"
                  onClick={() => handleDelete(node.stock_group_id)} 
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
                  title="Delete Stock Group"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Children nodes rendered with hierarchical connecting line */}
          {isExpanded && hasChildren && (
            <div className="ml-5 pl-3 border-l-2 border-border/50 space-y-1 mt-1">
              {renderTree(node.children, depth + 1)}
            </div>
          )}
        </div>
      )
    })
  }

  return (
    <div className="h-[calc(100vh-64px)] flex overflow-hidden relative">
      {/* Main Content (Tree View) */}
      <div className={cn(
        "flex-1 flex flex-col p-4 sm:p-6 overflow-y-auto transition-all duration-300",
        isPanelOpen && "lg:mr-[420px]"
      )}>
        {/* Header Section */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
          <div>
            <h1 className="text-2xl font-black tracking-tight text-foreground flex items-center gap-2">
              <FolderTree className="h-6 w-6 text-primary" />
              <span>Stock Groups</span>
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Hierarchical classification of your inventory items.
            </p>
          </div>
          {can('stock_groups', 'create') && (
            <button 
              type="button"
              onClick={() => openCreate()}
              className="bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2.5 rounded-xl font-bold text-xs flex items-center gap-2 shadow-xs transition-all cursor-pointer self-start sm:self-auto shrink-0"
            >
              <Plus className="h-4 w-4" /> Create Root Group
            </button>
          )}
        </div>

        {/* Search & Actions Bar */}
        <div className="bg-card border border-border rounded-2xl shadow-xs p-3.5 mb-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="relative w-full sm:w-80">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input 
              type="text" 
              value={searchQuery} 
              onChange={e => setSearchQuery(e.target.value)} 
              placeholder="Search stock groups or aliases..." 
              className="w-full bg-muted/40 border border-input rounded-xl pl-9 pr-8 py-2 text-xs focus:ring-2 focus:ring-primary focus:outline-none transition-all placeholder:text-muted-foreground"
            />
            {searchQuery && (
              <button 
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-0.5 cursor-pointer"
                title="Clear search"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto justify-between sm:justify-end">
            <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5" />
              <span>{groups.length} {groups.length === 1 ? 'group' : 'groups'}</span>
            </span>

            {allParentsCount > 0 && (
              <>
                <div className="h-3.5 w-px bg-border hidden sm:block" />
                <button
                  type="button"
                  onClick={isAllExpanded ? collapseAll : expandAll}
                  className="text-xs font-semibold px-2.5 py-1.5 rounded-xl border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                >
                  {isAllExpanded ? 'Collapse All' : 'Expand All'}
                </button>
              </>
            )}
          </div>
        </div>

        {/* Tree Container Card */}
        {loading ? (
          <div className="flex justify-center items-center p-16">
            <div className="animate-spin h-8 w-8 border-3 border-primary border-t-transparent rounded-full" />
          </div>
        ) : (
          <div className="bg-card border border-border rounded-2xl shadow-xs p-3.5 min-h-[500px]">
            {groups.length === 0 ? (
              <div className="text-center py-20 text-muted-foreground flex flex-col items-center">
                <Folder className="h-12 w-12 text-muted-foreground/30 mb-3" />
                <p className="font-bold text-sm text-foreground">No stock groups found</p>
                <p className="text-xs text-muted-foreground mt-0.5">Start structuring your inventory by creating a group.</p>
                {can('stock_groups', 'create') && (
                  <button 
                    type="button"
                    onClick={() => openCreate()} 
                    className="mt-3 text-xs font-bold text-primary hover:underline cursor-pointer"
                  >
                    + Create your first group
                  </button>
                )}
              </div>
            ) : filteredTree.length === 0 ? (
              <div className="text-center py-16 text-muted-foreground flex flex-col items-center">
                <Search className="h-10 w-10 text-muted-foreground/30 mb-2.5" />
                <p className="font-bold text-sm text-foreground">No groups match "{searchQuery}"</p>
                <button 
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="mt-2 text-xs font-bold text-primary hover:underline cursor-pointer"
                >
                  Clear search filter
                </button>
              </div>
            ) : (
              <div className="space-y-1">
                {renderTree(filteredTree)}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Backdrop overlay for mobile drawer */}
      {isPanelOpen && (
        <div 
          onClick={closePanel}
          className="fixed inset-0 bg-black/40 backdrop-blur-xs z-40 lg:hidden cursor-pointer"
        />
      )}

      {/* Slide-over Edit / Create Panel */}
      <div 
        className={cn(
          "fixed top-0 sm:top-[64px] right-0 bottom-0 w-full sm:w-[420px] bg-card border-l border-border shadow-2xl transition-transform duration-300 transform flex flex-col z-50",
          isPanelOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        <div className="px-6 py-4.5 border-b border-border flex items-center justify-between bg-muted/20 shrink-0">
          <div>
            <h2 className="text-base font-extrabold text-foreground">
              {isEditing ? 'Edit Stock Group' : 'Create Stock Group'}
            </h2>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {isEditing ? `Modifying group properties` : 'Define a new category in your inventory'}
            </p>
          </div>
          <button 
            type="button"
            onClick={closePanel} 
            className="w-8 h-8 rounded-full bg-muted/60 hover:bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            title="Close panel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <form id="group-form" onSubmit={handleSave} className="space-y-5">
            <div>
              <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1.5 block">
                Group Name <span className="text-destructive">*</span>
              </label>
              <input 
                type="text" 
                value={name} 
                onChange={e => setName(e.target.value)} 
                placeholder="e.g. NIRVAAN METALIKAS, Electronics" 
                className="w-full bg-background border border-input rounded-xl px-3.5 py-2.5 text-sm font-semibold focus:ring-2 focus:ring-primary focus:outline-none transition-all" 
                required 
                autoFocus={isPanelOpen}
              />
            </div>

            <div>
              <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1.5 block">
                Under Group (Parent)
              </label>
              <select 
                value={parentId} 
                onChange={e => setParentId(e.target.value ? Number(e.target.value) : '')} 
                className="w-full bg-background border border-input rounded-xl px-3.5 py-2.5 text-sm font-semibold focus:ring-2 focus:ring-primary focus:outline-none transition-all cursor-pointer"
              >
                <option value="">Primary (Top Level / Root)</option>
                {groups.filter(g => g.stock_group_id !== groupId).map(g => (
                  <option key={g.stock_group_id} value={g.stock_group_id}>{g.name}</option>
                ))}
              </select>
              <p className="text-[11px] text-muted-foreground mt-1">
                In Tally, <span className="font-semibold text-foreground">Primary</span> is the top level (no parent). Groups under Primary appear at the top level on the left.
              </p>
            </div>

            <div>
              <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1.5 block">
                Aliases (Comma separated)
              </label>
              <textarea 
                value={aliases} 
                onChange={e => setAliases(e.target.value)} 
                placeholder="e.g. Mobile Phones, Smartphones, Metals"
                rows={3} 
                className="w-full bg-background border border-input rounded-xl px-3.5 py-2.5 text-sm font-medium focus:ring-2 focus:ring-primary focus:outline-none resize-none transition-all" 
              />
              <p className="text-[11px] text-muted-foreground mt-1">Useful for alternative names when searching or syncing.</p>
            </div>

            <div className="flex items-center gap-3 pt-2 bg-muted/20 p-3 rounded-xl border border-border/60">
              <input 
                type="checkbox" 
                id="is_active" 
                checked={isActive} 
                onChange={e => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-border text-primary focus:ring-primary cursor-pointer"
              />
              <label htmlFor="is_active" className="text-xs font-bold text-foreground cursor-pointer">
                Group is Active
              </label>
            </div>
          </form>
        </div>

        <div className="p-4 border-t border-border bg-muted/10 flex items-center justify-end gap-2.5 shrink-0">
          <button 
            type="button" 
            onClick={closePanel} 
            className="px-4 py-2 rounded-xl font-bold text-xs hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button 
            type="submit" 
            form="group-form" 
            className="bg-primary hover:bg-primary/90 text-primary-foreground px-5 py-2 rounded-xl font-bold text-xs shadow-xs transition-all cursor-pointer"
          >
            {isEditing ? 'Save Changes' : 'Create Group'}
          </button>
        </div>
      </div>

      <DeleteGroupModal
        key={groupToDelete?.group_id ?? 'none'}
        group={groupToDelete}
        token={token}
        onClose={() => setGroupToDelete(null)}
        onChanged={() => {
          fetchGroups()
          if (groupToDelete && groupId === groupToDelete.group_id) closePanel()
        }}
        apiPath="/inventory/groups"
        memberLabel="stock item"
        title="Delete Stock Group"
      />
    </div>
  )
}
