import React, { useState, useRef, useCallback } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/esm/Page/AnnotationLayer.css'
import 'react-pdf/dist/esm/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`

const API_BASE = '/api'

export default function App() {
  const [pdfId, setPdfId] = useState(null)
  const [pdfUrl, setPdfUrl] = useState(null)
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [highlights, setHighlights] = useState([])
  const [relatedResults, setRelatedResults] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState('highlights')
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState(null)
  const [matchIndicator, setMatchIndicator] = useState(null)
  
  const fileInputRef = useRef(null)
  const pageRef = useRef(null)

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setIsUploading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`${API_BASE}/upload-pdf`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Upload failed')
      }

      const data = await response.json()
      setPdfId(data.pdf_id)
      setPdfUrl(`${API_BASE}/pdf/${data.pdf_id}`)
      setNumPages(data.page_count)
      setCurrentPage(1)
      setHighlights([])
      setRelatedResults(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsUploading(false)
    }
  }

  const handleTextSelection = useCallback(() => {
    const selection = window.getSelection()
    const text = selection?.toString().trim()
    
    if (!text || text.length < 3) return

    try {
      const range = selection.getRangeAt(0)
      const rects = range.getClientRects()
      if (rects.length === 0) return
      
      const rect = rects[0]
      const pageWrapper = pageRef.current
      
      if (!pageWrapper) return
      
      const pageRect = pageWrapper.getBoundingClientRect()
      
      const newHighlight = {
        id: Date.now().toString(),
        text,
        page: currentPage,
        position: {
          x: rect.left - pageRect.left,
          y: rect.top - pageRect.top,
          width: rect.width,
          height: rect.height
        }
      }

      setHighlights(prev => [...prev, newHighlight])
    } catch (e) {
      console.log('Selection error:', e)
    }
    selection.removeAllRanges()
  }, [currentPage])

  const removeHighlight = (id) => {
    setHighlights(prev => prev.filter(h => h.id !== id))
  }

  const findRelated = async (highlight) => {
    if (!pdfId) return

    setIsLoading(true)
    setError(null)
    setSearchQuery(highlight.text)
    setActiveTab('results')

    try {
      const response = await fetch(`${API_BASE}/related-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pdf_id: pdfId,
          query: highlight.text,
          top_k: 5
        })
      })

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Search failed')
      }

      const data = await response.json()
      setRelatedResults(data.results)
    } catch (err) {
      setError(err.message)
      setRelatedResults([])
    } finally {
      setIsLoading(false)
    }
  }

  const jumpToMatch = (result) => {
    setCurrentPage(result.page_number)
    
    const bbox = result.bounding_box
    if (bbox && bbox.x0 > 0) {
      setMatchIndicator({
        x: bbox.x0,
        y: bbox.y0,
        width: bbox.x1 - bbox.x0,
        height: bbox.y1 - bbox.y0
      })
      
      setTimeout(() => setMatchIndicator(null), 3000)
    }
  }

  const getConfidenceClass = (confidence) => {
    if (confidence >= 0.7) return 'confidence-high'
    if (confidence >= 0.5) return 'confidence-medium'
    return 'confidence-low'
  }

  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages)
  }

  return (
    <div className="app">
      <header className="header">
        <h1>📄 PDF Semantic Search</h1>
        <div className="upload-section">
          {pdfId && <span>Loaded: {numPages} pages</span>}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileUpload}
          />
          <button 
            className="upload-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            {isUploading ? 'Uploading...' : 'Upload PDF'}
          </button>
        </div>
      </header>

      <div className="main-content">
        <div className="pdf-container">
          {!pdfUrl ? (
            <div className="upload-prompt">
              <div className="upload-prompt-icon">📁</div>
              <h2>No PDF Loaded</h2>
              <p>Upload a PDF to get started</p>
            </div>
          ) : (
            <>
              <div className="pdf-toolbar">
                <button 
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage <= 1}
                >
                  ← Prev
                </button>
                <span>Page {currentPage} of {numPages}</span>
                <button 
                  onClick={() => setCurrentPage(p => Math.min(numPages, p + 1))}
                  disabled={currentPage >= numPages}
                >
                  Next →
                </button>
              </div>

              <div className="pdf-viewer" onMouseUp={handleTextSelection}>
                <div className="pdf-page-wrapper" ref={pageRef}>
                  <Document
                    file={pdfUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                  >
                    <Page 
                      pageNumber={currentPage} 
                      renderTextLayer={true}
                      renderAnnotationLayer={true}
                    />
                  </Document>

                  {highlights
                    .filter(h => h.page === currentPage)
                    .map(h => (
                      <div
                        key={h.id}
                        className="highlight-overlay user-highlight"
                        style={{
                          left: h.position.x,
                          top: h.position.y,
                          width: h.position.width,
                          height: h.position.height
                        }}
                      />
                    ))}

                  {matchIndicator && (
                    <div
                      className="match-indicator"
                      style={{
                        left: matchIndicator.x,
                        top: matchIndicator.y,
                        width: Math.max(matchIndicator.width, 100),
                        height: Math.max(matchIndicator.height, 20)
                      }}
                    />
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="side-panel">
          <div className="panel-tabs">
            <button 
              className={`panel-tab ${activeTab === 'highlights' ? 'active' : ''}`}
              onClick={() => setActiveTab('highlights')}
            >
              Highlights ({highlights.length})
            </button>
            <button 
              className={`panel-tab ${activeTab === 'results' ? 'active' : ''}`}
              onClick={() => setActiveTab('results')}
            >
              Results
            </button>
          </div>

          <div className="panel-content">
            {activeTab === 'highlights' ? (
              highlights.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-icon">✨</div>
                  <h3>No Highlights Yet</h3>
                  <p>Select text in the PDF to create a highlight</p>
                </div>
              ) : (
                highlights.map(h => (
                  <div key={h.id} className="highlight-item">
                    <div className="highlight-header">
                      <span className="highlight-page">Page {h.page}</span>
                    </div>
                    <p className="highlight-text">
                      {h.text.length > 150 ? h.text.slice(0, 150) + '...' : h.text}
                    </p>
                    <div className="highlight-actions">
                      <button 
                        className="find-related-btn"
                        onClick={() => findRelated(h)}
                      >
                        🔍 Find Related
                      </button>
                      <button 
                        className="remove-btn"
                        onClick={() => removeHighlight(h.id)}
                      >
                        ✕ Remove
                      </button>
                    </div>
                  </div>
                ))
              )
            ) : (
              <>
                {searchQuery && (
                  <>
                    <button 
                      className="back-btn"
                      onClick={() => setActiveTab('highlights')}
                    >
                      ← Back to Highlights
                    </button>
                    <div className="query-display">
                      <strong>Query:</strong> "{searchQuery.slice(0, 100)}{searchQuery.length > 100 ? '...' : ''}"
                    </div>
                  </>
                )}

                {error && (
                  <div className="error-state">
                    <h4>⚠️ Error</h4>
                    <p>{error}</p>
                  </div>
                )}

                {isLoading ? (
                  <div className="loading-skeleton">
                    {[1, 2, 3].map(i => (
                      <div key={i} className="skeleton-item">
                        <div className="skeleton-line" />
                        <div className="skeleton-line" />
                        <div className="skeleton-line" />
                      </div>
                    ))}
                  </div>
                ) : relatedResults === null ? (
                  <div className="empty-state">
                    <div className="empty-state-icon">🔎</div>
                    <h3>No Search Yet</h3>
                    <p>Click "Find Related" on a highlight to search</p>
                  </div>
                ) : relatedResults.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-state-icon">🤷</div>
                    <h3>No Related Text Found</h3>
                    <p>Try a different highlight or search term</p>
                  </div>
                ) : (
                  relatedResults.map((result, idx) => (
                    <div key={idx} className="result-item">
                      <div className="result-header">
                        <span className="result-page">Page {result.page_number}</span>
                        <span className={`result-confidence ${getConfidenceClass(result.confidence)}`}>
                          {(result.confidence * 100).toFixed(0)}% match
                        </span>
                      </div>
                      <p className="result-snippet">{result.snippet}</p>
                      <p className="result-rationale">{result.rationale}</p>
                      <button 
                        className="jump-btn"
                        onClick={() => jumpToMatch(result)}
                      >
                        📍 Jump to Location
                      </button>
                    </div>
                  ))
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
