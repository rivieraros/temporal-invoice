import { useState } from 'react'
import { FileText, FileSpreadsheet, ZoomIn, ZoomOut, Download, ChevronLeft, ChevronRight } from 'lucide-react'

interface PDFViewerProps {
  packageId: string
  selectedInvoiceId?: string
  statementUrl?: string
  invoiceUrls?: Record<string, string>
}

type ViewMode = 'statement' | 'invoice'

export function PDFViewer({ packageId, selectedInvoiceId }: PDFViewerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('statement')
  const [zoom, setZoom] = useState(100)
  const [page, setPage] = useState(1)
  const totalPages = viewMode === 'statement' ? 2 : 1 // Placeholder

  const handleZoomIn = () => setZoom((z) => Math.min(z + 25, 200))
  const handleZoomOut = () => setZoom((z) => Math.max(z - 25, 50))

  return (
    <div className="h-full flex flex-col bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between p-3 border-b border-slate-700 bg-slate-800">
        {/* View Mode Toggle */}
        <div className="flex items-center gap-1 bg-slate-900 rounded-lg p-1">
          <button
            onClick={() => setViewMode('statement')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              viewMode === 'statement'
                ? 'bg-purple-500 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <FileSpreadsheet size={14} />
            Statement
          </button>
          <button
            onClick={() => setViewMode('invoice')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              viewMode === 'invoice'
                ? 'bg-purple-500 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <FileText size={14} />
            Invoice
          </button>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleZoomOut}
            className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
          >
            <ZoomOut size={16} />
          </button>
          <span className="text-sm text-slate-400 w-12 text-center">{zoom}%</span>
          <button
            onClick={handleZoomIn}
            className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
          >
            <ZoomIn size={16} />
          </button>
          <div className="w-px h-4 bg-slate-700 mx-2" />
          <button className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white transition-colors">
            <Download size={16} />
          </button>
        </div>
      </div>

      {/* PDF Content Placeholder */}
      <div className="flex-1 overflow-auto p-4">
        <div
          className="mx-auto bg-white rounded-lg shadow-xl transition-transform"
          style={{
            width: `${(8.5 * zoom) / 100 * 72}px`,
            minHeight: `${(11 * zoom) / 100 * 72}px`,
          }}
        >
          {/* Placeholder content - would be actual PDF rendering */}
          <div className="p-8 text-slate-800">
            <div className="text-center mb-8">
              <h3 className="text-lg font-bold text-slate-900">
                {viewMode === 'statement' ? 'Statement of Notes' : 'Feed Invoice'}
              </h3>
              <p className="text-sm text-slate-500">Package: {packageId}</p>
              {viewMode === 'invoice' && selectedInvoiceId && (
                <p className="text-sm text-slate-500">Invoice: {selectedInvoiceId}</p>
              )}
            </div>

            {/* Placeholder document preview */}
            <div className="space-y-4">
              <div className="h-4 bg-slate-200 rounded w-3/4" />
              <div className="h-4 bg-slate-200 rounded w-1/2" />
              <div className="h-4 bg-slate-200 rounded w-5/6" />
              <div className="h-32 bg-slate-100 rounded border border-slate-200 mt-6" />
              <div className="h-4 bg-slate-200 rounded w-2/3" />
              <div className="h-4 bg-slate-200 rounded w-3/4" />
              <div className="h-24 bg-slate-100 rounded border border-slate-200" />
            </div>

            <div className="mt-8 text-center text-sm text-slate-400">
              PDF viewer placeholder - actual PDF would render here
            </div>
          </div>
        </div>
      </div>

      {/* Page Navigation */}
      <div className="flex items-center justify-center gap-4 p-3 border-t border-slate-700 bg-slate-800">
        <button
          onClick={() => setPage((p) => Math.max(p - 1, 1))}
          disabled={page <= 1}
          className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="text-sm text-slate-400">
          Page {page} of {totalPages}
        </span>
        <button
          onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
          disabled={page >= totalPages}
          className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  )
}
