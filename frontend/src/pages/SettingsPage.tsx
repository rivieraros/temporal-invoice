import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  Settings,
  Database,
  Users,
  Building2,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Plus,
  Search,
  Edit2,
  Trash2,
  ExternalLink,
  Clock,
  Zap,
  ChevronRight,
  Shield,
  Key,
  Server,
  Tag,
} from 'lucide-react'
import { fetchConfiguration, testConnector } from '../api/client'
import type {
  ConfigurationResponse,
  ConnectorConfig,
  EntityMapping,
  VendorMapping,
  ConnectorTestResult,
} from '../types'

type SettingsTab = 'connectors' | 'entities' | 'vendors'

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('connectors')
  const [config, setConfig] = useState<ConfigurationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [testingConnector, setTestingConnector] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<ConnectorTestResult | null>(null)
  const [entityFilter, setEntityFilter] = useState<string>('')
  const [vendorSearch, setVendorSearch] = useState<string>('')

  useEffect(() => {
    loadConfiguration()
  }, [])

  const loadConfiguration = async () => {
    try {
      setLoading(true)
      const data = await fetchConfiguration()
      setConfig(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load configuration')
    } finally {
      setLoading(false)
    }
  }

  const handleTestConnector = async (connectorId: string) => {
    setTestingConnector(connectorId)
    setTestResult(null)
    try {
      const result = await testConnector(connectorId)
      setTestResult(result)
    } catch (err) {
      setTestResult({
        success: false,
        connector_id: connectorId,
        latency_ms: 0,
        message: err instanceof Error ? err.message : 'Connection test failed',
        details: {},
      })
    } finally {
      setTestingConnector(null)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected':
        return 'text-emerald-400 bg-emerald-500/20'
      case 'configured':
        return 'text-amber-400 bg-amber-500/20'
      case 'error':
        return 'text-red-400 bg-red-500/20'
      default:
        return 'text-slate-400 bg-slate-500/20'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'connected':
        return <CheckCircle size={16} className="text-emerald-400" />
      case 'configured':
        return <AlertTriangle size={16} className="text-amber-400" />
      case 'error':
        return <XCircle size={16} className="text-red-400" />
      default:
        return <AlertTriangle size={16} className="text-slate-400" />
    }
  }

  const filteredVendors = config?.vendors.filter((v) => {
    const matchesEntity = !entityFilter || v.entity_id === entityFilter
    const matchesSearch =
      !vendorSearch ||
      v.alias_original.toLowerCase().includes(vendorSearch.toLowerCase()) ||
      v.vendor_name.toLowerCase().includes(vendorSearch.toLowerCase()) ||
      v.vendor_number.toLowerCase().includes(vendorSearch.toLowerCase())
    return matchesEntity && matchesSearch
  })

  const tabs = [
    { id: 'connectors' as const, label: 'BC Connection', icon: Database, count: config?.connectors.length },
    { id: 'entities' as const, label: 'Entity Mapping', icon: Building2, count: config?.entities.length },
    { id: 'vendors' as const, label: 'Vendor Mapping', icon: Users, count: config?.vendors.length },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="animate-spin text-purple-500" size={32} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <XCircle size={48} className="text-red-400 mx-auto mb-4" />
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={loadConfiguration}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-500"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/mission-control"
            className="p-2 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <ArrowLeft size={20} className="text-slate-400" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <Settings className="text-purple-400" size={28} />
              Configuration
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Manage ERP connections, entity routing, and vendor mappings
            </p>
          </div>
        </div>
        <button
          onClick={loadConfiguration}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors"
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
              <Zap size={20} className="text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{config?.stats.connectors_connected || 0}</p>
              <p className="text-sm text-slate-400">Connected</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <Building2 size={20} className="text-purple-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{config?.stats.active_entities || 0}</p>
              <p className="text-sm text-slate-400">Active Entities</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <Users size={20} className="text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{config?.stats.total_vendor_mappings || 0}</p>
              <p className="text-sm text-slate-400">Vendor Mappings</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
              <Shield size={20} className="text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">OAuth 2.0</p>
              <p className="text-sm text-slate-400">Auth Method</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-700">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === tab.id
                  ? 'text-purple-400 border-purple-500'
                  : 'text-slate-400 border-transparent hover:text-slate-300 hover:border-slate-600'
              }`}
            >
              <tab.icon size={18} />
              {tab.label}
              {tab.count !== undefined && (
                <span
                  className={`px-2 py-0.5 rounded-full text-xs ${
                    activeTab === tab.id ? 'bg-purple-500/20' : 'bg-slate-700'
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="min-h-[500px]">
        {/* Connectors Tab */}
        {activeTab === 'connectors' && (
          <div className="space-y-6">
            {config?.connectors.map((connector) => (
              <ConnectorCard
                key={connector.id}
                connector={connector}
                onTest={() => handleTestConnector(connector.id)}
                testing={testingConnector === connector.id}
                testResult={testResult?.connector_id === connector.id ? testResult : null}
                getStatusColor={getStatusColor}
                getStatusIcon={getStatusIcon}
              />
            ))}

            {/* Add Connector Button */}
            <button className="w-full p-6 border-2 border-dashed border-slate-700 rounded-xl text-slate-400 hover:text-purple-400 hover:border-purple-500/50 transition-colors flex items-center justify-center gap-3">
              <Plus size={20} />
              Add New Connector
            </button>
          </div>
        )}

        {/* Entities Tab */}
        {activeTab === 'entities' && (
          <div className="space-y-4">
            {/* Actions Bar */}
            <div className="flex items-center justify-between">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search entities..."
                  className="pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
                />
              </div>
              <button className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-500 transition-colors">
                <Plus size={16} />
                Add Entity
              </button>
            </div>

            {/* Entity Cards */}
            <div className="grid grid-cols-1 gap-4">
              {config?.entities.map((entity) => (
                <EntityCard key={entity.id} entity={entity} />
              ))}
            </div>
          </div>
        )}

        {/* Vendors Tab */}
        {activeTab === 'vendors' && (
          <div className="space-y-4">
            {/* Filters */}
            <div className="flex items-center gap-4">
              <div className="relative flex-1">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search vendor name, alias, or number..."
                  value={vendorSearch}
                  onChange={(e) => setVendorSearch(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
                />
              </div>
              <select
                value={entityFilter}
                onChange={(e) => setEntityFilter(e.target.value)}
                className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-purple-500"
              >
                <option value="">All Entities</option>
                {config?.entities.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.entity_code} - {e.entity_name}
                  </option>
                ))}
              </select>
              <button className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-500 transition-colors">
                <Plus size={16} />
                Add Mapping
              </button>
            </div>

            {/* Vendor Table */}
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700 bg-slate-800">
                    <th className="text-left p-4 text-sm font-medium text-slate-400">Alias</th>
                    <th className="text-left p-4 text-sm font-medium text-slate-400">Vendor</th>
                    <th className="text-left p-4 text-sm font-medium text-slate-400">Entity</th>
                    <th className="text-center p-4 text-sm font-medium text-slate-400">Matches</th>
                    <th className="text-left p-4 text-sm font-medium text-slate-400">Created By</th>
                    <th className="text-right p-4 text-sm font-medium text-slate-400">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredVendors?.map((vendor) => (
                    <VendorRow key={vendor.id} vendor={vendor} />
                  ))}
                </tbody>
              </table>
              {filteredVendors?.length === 0 && (
                <div className="p-8 text-center text-slate-400">
                  No vendor mappings found matching your criteria
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

interface ConnectorCardProps {
  connector: ConnectorConfig
  onTest: () => void
  testing: boolean
  testResult: ConnectorTestResult | null
  getStatusColor: (status: string) => string
  getStatusIcon: (status: string) => React.ReactNode
}

function ConnectorCard({
  connector,
  onTest,
  testing,
  testResult,
  getStatusColor,
  getStatusIcon,
}: ConnectorCardProps) {
  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <Database size={28} className="text-white" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">{connector.name}</h3>
              <p className="text-sm text-slate-400">{connector.connector_type.replace('_', ' ').toUpperCase()}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${getStatusColor(
                connector.status
              )}`}
            >
              {getStatusIcon(connector.status)}
              {connector.status.charAt(0).toUpperCase() + connector.status.slice(1)}
            </span>
            <button className="p-2 rounded-lg hover:bg-slate-700 transition-colors">
              <Edit2 size={16} className="text-slate-400" />
            </button>
          </div>
        </div>
      </div>

      {/* Connection Details */}
      <div className="p-6 grid grid-cols-3 gap-6">
        <div className="space-y-4">
          <div className="flex items-center gap-3 text-sm">
            <Key size={16} className="text-slate-500" />
            <span className="text-slate-400">Tenant ID:</span>
            <span className="text-white font-mono">{connector.tenant_id || '—'}</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <Shield size={16} className="text-slate-500" />
            <span className="text-slate-400">Client ID:</span>
            <span className="text-white font-mono">{connector.client_id || '—'}</span>
          </div>
        </div>
        <div className="space-y-4">
          <div className="flex items-center gap-3 text-sm">
            <Building2 size={16} className="text-slate-500" />
            <span className="text-slate-400">Company:</span>
            <span className="text-white">{connector.company_id || '—'}</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <Server size={16} className="text-slate-500" />
            <span className="text-slate-400">Environment:</span>
            <span className="text-white capitalize">{connector.environment}</span>
          </div>
        </div>
        <div className="space-y-4">
          <div className="flex items-center gap-3 text-sm">
            <Clock size={16} className="text-slate-500" />
            <span className="text-slate-400">Last Connected:</span>
            <span className="text-white">
              {connector.last_connected
                ? new Date(connector.last_connected).toLocaleString()
                : '—'}
            </span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <RefreshCw size={16} className="text-slate-500" />
            <span className="text-slate-400">Last Sync:</span>
            <span className="text-white">
              {connector.last_sync ? new Date(connector.last_sync).toLocaleString() : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* Test Result */}
      {testResult && (
        <div
          className={`mx-6 mb-6 p-4 rounded-lg ${
            testResult.success
              ? 'bg-emerald-500/10 border border-emerald-500/30'
              : 'bg-red-500/10 border border-red-500/30'
          }`}
        >
          <div className="flex items-center gap-3">
            {testResult.success ? (
              <CheckCircle size={20} className="text-emerald-400" />
            ) : (
              <XCircle size={20} className="text-red-400" />
            )}
            <div>
              <p className={testResult.success ? 'text-emerald-400' : 'text-red-400'}>
                {testResult.message}
              </p>
              {testResult.success && testResult.details && (
                <p className="text-sm text-slate-400 mt-1">
                  Latency: {testResult.latency_ms}ms | Companies: {testResult.details.company_count as number} |
                  Vendors: {testResult.details.vendor_count as number} | GL Accounts:{' '}
                  {testResult.details.gl_account_count as number}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="px-6 py-4 bg-slate-800/50 border-t border-slate-700 flex items-center justify-between">
        <button
          onClick={onTest}
          disabled={testing}
          className="flex items-center gap-2 px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors disabled:opacity-50"
        >
          {testing ? (
            <RefreshCw size={16} className="animate-spin" />
          ) : (
            <Zap size={16} />
          )}
          {testing ? 'Testing...' : 'Test Connection'}
        </button>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-2 px-4 py-2 text-slate-400 hover:text-white transition-colors">
            <ExternalLink size={16} />
            Open in Azure Portal
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-500 transition-colors">
            <RefreshCw size={16} />
            Sync Now
          </button>
        </div>
      </div>
    </div>
  )
}

interface EntityCardProps {
  entity: EntityMapping
}

function EntityCard({ entity }: EntityCardProps) {
  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6 hover:border-purple-500/50 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center ${
              entity.is_active ? 'bg-purple-500/20' : 'bg-slate-700'
            }`}
          >
            <Building2 size={24} className={entity.is_active ? 'text-purple-400' : 'text-slate-500'} />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-semibold text-white">{entity.entity_name}</h3>
              <span className="px-2 py-0.5 bg-slate-700 text-slate-300 rounded text-sm font-mono">
                {entity.entity_code}
              </span>
              {entity.is_active ? (
                <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded text-xs">
                  Active
                </span>
              ) : (
                <span className="px-2 py-0.5 bg-slate-600 text-slate-400 rounded text-xs">
                  Inactive
                </span>
              )}
            </div>
            <p className="text-sm text-slate-400 mt-1">BC Company: {entity.bc_company_id}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="p-2 rounded-lg hover:bg-slate-700 transition-colors">
            <Edit2 size={16} className="text-slate-400" />
          </button>
          <button className="p-2 rounded-lg hover:bg-slate-700 transition-colors">
            <Trash2 size={16} className="text-slate-400" />
          </button>
          <ChevronRight size={20} className="text-slate-500" />
        </div>
      </div>

      {/* Details Grid */}
      <div className="mt-6 grid grid-cols-4 gap-6">
        {/* Aliases */}
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Aliases</p>
          <div className="flex flex-wrap gap-1">
            {entity.aliases.map((alias, i) => (
              <span
                key={i}
                className="px-2 py-0.5 bg-slate-700 text-slate-300 rounded text-xs"
              >
                {alias}
              </span>
            ))}
          </div>
        </div>

        {/* Routing Keys */}
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Routing Keys</p>
          <div className="flex flex-wrap gap-1">
            {entity.routing_keys.slice(0, 3).map((key, i) => (
              <span
                key={i}
                className="px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs font-mono"
              >
                {key}
              </span>
            ))}
            {entity.routing_keys.length > 3 && (
              <span className="px-2 py-0.5 bg-slate-700 text-slate-400 rounded text-xs">
                +{entity.routing_keys.length - 3}
              </span>
            )}
          </div>
        </div>

        {/* Dimensions */}
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Default Dimensions</p>
          <div className="flex flex-wrap gap-1">
            {Object.entries(entity.default_dimensions).map(([key, value]) => (
              <span
                key={key}
                className="px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded text-xs"
              >
                <Tag size={10} className="inline mr-1" />
                {key}: {value}
              </span>
            ))}
          </div>
        </div>

        {/* Stats */}
        <div className="text-right">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Activity</p>
          <p className="text-white font-semibold">{entity.invoice_count.toLocaleString()} invoices</p>
          <p className="text-xs text-slate-400">
            Last used:{' '}
            {entity.last_used ? new Date(entity.last_used).toLocaleDateString() : '—'}
          </p>
        </div>
      </div>
    </div>
  )
}

interface VendorRowProps {
  vendor: VendorMapping
}

function VendorRow({ vendor }: VendorRowProps) {
  return (
    <tr className="border-b border-slate-700/50 hover:bg-slate-800/50 transition-colors">
      <td className="p-4">
        <div>
          <p className="text-white font-medium">{vendor.alias_original}</p>
          <p className="text-xs text-slate-500 font-mono">{vendor.alias_normalized}</p>
        </div>
      </td>
      <td className="p-4">
        <div>
          <p className="text-white">{vendor.vendor_name}</p>
          <p className="text-xs text-slate-400 font-mono">{vendor.vendor_number}</p>
        </div>
      </td>
      <td className="p-4">
        <span className="px-2 py-1 bg-slate-700 text-slate-300 rounded text-sm">
          {vendor.entity_name}
        </span>
      </td>
      <td className="p-4 text-center">
        <span className="text-white font-medium">{vendor.match_count}</span>
      </td>
      <td className="p-4">
        <div className="flex items-center gap-2">
          <span
            className={`px-2 py-0.5 rounded text-xs ${
              vendor.created_by === 'system'
                ? 'bg-blue-500/20 text-blue-400'
                : 'bg-purple-500/20 text-purple-400'
            }`}
          >
            {vendor.created_by}
          </span>
          {vendor.created_at && (
            <span className="text-xs text-slate-500">
              {new Date(vendor.created_at).toLocaleDateString()}
            </span>
          )}
        </div>
      </td>
      <td className="p-4 text-right">
        <div className="flex items-center justify-end gap-1">
          <button className="p-2 rounded-lg hover:bg-slate-700 transition-colors">
            <Edit2 size={14} className="text-slate-400" />
          </button>
          <button className="p-2 rounded-lg hover:bg-slate-700 transition-colors">
            <Trash2 size={14} className="text-slate-400" />
          </button>
        </div>
      </td>
    </tr>
  )
}
