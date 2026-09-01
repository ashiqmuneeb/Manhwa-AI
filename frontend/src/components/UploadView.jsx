import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { FileText, Sparkles, AlertCircle, Loader, Type, Upload, BookOpen, Trash2, Edit3, X, Check } from 'lucide-react'

const API_BASE = 'http://localhost:8000'

function UploadView({ onUploadSuccess }) {
  const [title, setTitle] = useState('')
  const [rawText, setRawText] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [inputMode, setInputMode] = useState('file') // 'file' | 'text'
  const [maxPages, setMaxPages] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  
  // Grid Archives Bookshelf state
  const [novels, setNovels] = useState([])
  const [loadingShelf, setLoadingShelf] = useState(true)

  // Lined Manuscript Sheets state
  const [previewPages, setPreviewPages] = useState([])
  const [isEditingPreviews, setIsEditingPreviews] = useState(false)
  
  const fileInputRef = useRef(null)

  // Load Novels Shelf on mount
  const fetchNovels = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/novels`)
      setNovels(response.data || [])
    } catch (err) {
      console.error('Failed to load novels shelf:', err)
    } finally {
      setLoadingShelf(false)
    }
  }

  useEffect(() => {
    fetchNovels()
  }, [])

  // Handle file select
  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file) {
      const name = file.name.toLowerCase()
      if (!name.endsWith('.txt') && !name.endsWith('.pdf')) {
        setError('Please upload a standard text file (.txt) or document (.pdf).')
        setSelectedFile(null)
        return
      }
      setSelectedFile(file)
      setError(null)
      
      // Autofill title if empty
      if (!title) {
        const cleanName = file.name.replace(/\.[^/.]+$/, "")
        setTitle(cleanName)
      }
    }
  }

  // Handle preview preparation (splits text / calls extraction API)
  const handlePrepareManuscript = async (e) => {
    e.preventDefault()
    if (!title.trim()) {
      setError('Please provide a manuscript title.')
      return
    }
    
    if (inputMode === 'file' && !selectedFile) {
      setError('Please select a file to parse.')
      return
    }
    if (inputMode === 'text' && !rawText.trim()) {
      setError('Please enter some manuscript text.')
      return
    }

    setLoading(true)
    setError(null)

    try {
      let pages = []
      
      if (inputMode === 'file') {
        const formData = new FormData()
        formData.append('file', selectedFile)
        formData.append('max_chapters', maxPages)
        
        // Extract text on backend first
        const response = await axios.post(`${API_BASE}/api/extract-text`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        const pagesData = response.data.pages || []
        
        pages = pagesData.map((pageObj, idx) => ({
          id: `page-${idx}-${Date.now()}`,
          pageNum: pageObj.pageNum || (idx + 1),
          text: typeof pageObj === 'string' ? pageObj : pageObj.text,
          image_url: pageObj.image_url || null,
          is_comic: pageObj.is_comic || false
        }))
      } else {
        // Text mode - split by paragraphs and group every 5 into a page
        const paragraphs = rawText.split('\n').map(p => p.trim()).filter(p => p.length > 0)
        if (paragraphs.length === 0) {
          throw new Error('Could not parse any paragraphs from the text.')
        }
        for (let i = 0; i < paragraphs.length; i += 5) {
          const chunk = paragraphs.slice(i, i + 5).join('\n\n')
          pages.push({
            id: `page-${Math.floor(i/5)}-${Date.now()}`,
            pageNum: Math.floor(i/5) + 1,
            text: chunk,
            image_url: null,
            is_comic: false
          })
        }
      }

      if (pages.length === 0) {
        throw new Error('No readable text pages could be compiled.')
      }

      setPreviewPages(pages)
      setIsEditingPreviews(true)
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || err.message || 'Failed to extract text document.')
    } finally {
      setLoading(false)
    }
  }

  // Handle final submission of edited pages
  const handleCompileManhwa = async () => {
    const activePages = previewPages.filter(p => p.text.trim().length > 0)
    if (activePages.length === 0) {
      setError('No manuscript pages left to compile.')
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Re-join active pages text
      const compiledText = activePages.map(p => p.text.trim()).join('\n\n')
      
      const formData = new FormData()
      formData.append('title', title.trim())
      formData.append('raw_text', compiledText)
      formData.append('max_chapters', maxPages)
      formData.append('pages_json', JSON.stringify(activePages))

      const response = await axios.post(`${API_BASE}/api/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      if (response.data && response.data.success) {
        onUploadSuccess({
          chapter_id: response.data.chapter_id,
          title: title.trim()
        })
      } else {
        setError('Compilation failed.')
      }
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || 'Failed to compile chapters.')
    } finally {
      setLoading(false)
    }
  }

  // Delete a page locally
  const handleDeletePage = (pageId) => {
    setPreviewPages(prev => prev.filter(p => p.id !== pageId))
  }

  // Crop page text to cursor selection
  const handleCropPage = (pageId) => {
    const textarea = document.getElementById(`textarea-${pageId}`)
    if (!textarea) return

    const start = textarea.selectionStart
    const end = textarea.selectionEnd

    if (start !== end) {
      const selectedText = textarea.value.substring(start, end).trim()
      if (selectedText.length > 0) {
        setPreviewPages(prev => prev.map(p => p.id === pageId ? { ...p, text: selectedText } : p))
      } else {
        alert("Selected text area is empty.")
      }
    } else {
      alert("Please highlight/select a portion of the text inside the page to crop first!")
    }
  }

  // Edit page text inline
  const handlePageTextChange = (pageId, newText) => {
    setPreviewPages(prev => prev.map(p => p.id === pageId ? { ...p, text: newText } : p))
  }

  // Delete compiled novel from Database
  const handleDeleteNovel = async (e, novelId) => {
    e.stopPropagation() // Prevent reopening novel reader
    if (!window.confirm("Are you sure you want to delete this novel manuscript? This action cascades and deletes all compiled images.")) return

    try {
      await axios.delete(`${API_BASE}/api/novels/${novelId}`)
      // Refetch shelf items
      fetchNovels()
    } catch (err) {
      console.error('Delete novel failed:', err)
      alert('Failed to delete novel.')
    }
  }

  // Open existing compiled novel
  const handleOpenNovel = (novel) => {
    if (!novel.chapter_id) {
      alert("No compiled chapters found for this manuscript.")
      return
    }
    onUploadSuccess({
      chapter_id: novel.chapter_id,
      title: novel.title
    })
  }

  const bookColorClasses = ['book-purple', 'book-red', 'book-green', 'book-amber']

  return (
    <div style={{ maxWidth: '900px', margin: '30px auto', padding: '0 20px', width: '100%' }}>
      
      {/* 1. Manhwa Archives Bookshelf Section */}
      {!isEditingPreviews && !loadingShelf && novels.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 className="bookshelf-title">
            <BookOpen size={18} />
            Manhwa Archives Shelf
          </h3>
          <div className="bookshelf-container">
            <div className="shelf-row">
              {novels.map((novel, idx) => (
                <div 
                  key={novel.id} 
                  className={`book-spine-cover ${bookColorClasses[idx % bookColorClasses.length]}`}
                  onClick={() => handleOpenNovel(novel)}
                  title={`Open: ${novel.title}`}
                >
                  {/* Spine delete button */}
                  <button 
                    className="btn-book-delete"
                    onClick={(e) => handleDeleteNovel(e, novel.id)}
                    title="Delete Novel"
                  >
                    <Trash2 size={10} />
                  </button>

                  <div className="book-title">{novel.title}</div>
                  <div className="book-date">
                    {novel.created_at ? new Date(novel.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : 'Archive'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 2. Main Desk Mat workspace */}
      <div className="desk-mat">
        
        {/* State A: File Upload & Inputs */}
        {!isEditingPreviews ? (
          <div className="manuscript-page">
            <div className="paper-clip"></div>
            
            <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '26px', textAlign: 'center', marginBottom: '6px', color: '#1a1816', fontWeight: 700 }}>
              Novel-to-Manhwa Studio
            </h2>
            <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--text-muted-dark)', marginBottom: '28px', fontStyle: 'italic' }}>
              Upload your PDF/TXT draft. Customize your panel scenes before generation.
            </p>

            <form onSubmit={handlePrepareManuscript} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              
              {/* Title */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted-dark)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Manuscript Title
                </span>
                <input 
                  type="text" 
                  placeholder="e.g. Solo Leveling Chapter 1" 
                  className="typewriter-input"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  disabled={loading}
                />
              </div>

              {/* Max Pages (Limits for PDF/TXT) */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted-dark)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Max Pages / Chapters to Extract
                </span>
                <input 
                  type="number" 
                  min={1}
                  className="typewriter-input"
                  value={maxPages}
                  onChange={(e) => setMaxPages(parseInt(e.target.value, 10) || 1)}
                  disabled={loading}
                />
                <span style={{ fontSize: '11px', color: 'var(--text-muted-dark)', fontStyle: 'italic', marginTop: '2px' }}>
                  Limits PDF page parsing or text scene counts (default is 5).
                </span>
              </div>

              {/* Mode Toggles */}
              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => setInputMode('file')}
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid rgba(0,0,0,0.1)',
                    background: inputMode === 'file' ? '#e2dcd0' : 'transparent',
                    fontFamily: 'var(--font-serif)',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    color: 'var(--text-dark)'
                  }}
                >
                  <Upload size={14} />
                  Upload PDF / TXT
                </button>
                <button
                  type="button"
                  onClick={() => setInputMode('text')}
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid rgba(0,0,0,0.1)',
                    background: inputMode === 'text' ? '#e2dcd0' : 'transparent',
                    fontFamily: 'var(--font-serif)',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    color: 'var(--text-dark)'
                  }}
                >
                  <Type size={14} />
                  Type Direct
                </button>
              </div>

              {/* File Dropzone */}
              {inputMode === 'file' && (
                <div 
                  className="manila-dropzone"
                  onClick={() => fileInputRef.current.click()}
                  style={{ padding: '36px 20px' }}
                >
                  <input 
                    ref={fileInputRef}
                    type="file" 
                    style={{ display: 'none' }} 
                    onChange={handleFileChange}
                    accept=".txt,.pdf"
                    disabled={loading}
                  />
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                    <FileText size={28} color="#856b3e" style={{ opacity: 0.8 }} />
                    <div>
                      {selectedFile ? (
                        <p style={{ fontSize: '13px', fontWeight: 700, color: '#3b2f15' }}>
                          Selected: {selectedFile.name}
                        </p>
                      ) : (
                        <p style={{ fontSize: '13px', fontWeight: 600 }}>
                          Drop manuscript file here
                        </p>
                      )}
                      <p style={{ fontSize: '11px', opacity: 0.7 }}>
                        Supports .txt and .pdf files
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Text Area */}
              {inputMode === 'text' && (
                <div style={{ border: '1px solid rgba(110, 100, 90, 0.2)', borderRadius: '6px', padding: '16px', background: 'rgba(255,255,255,0.15)' }}>
                  <textarea 
                    placeholder="Enter or paste novel paragraphs here..."
                    className="typewriter-textarea"
                    value={rawText}
                    onChange={(e) => setRawText(e.target.value)}
                    disabled={loading}
                  />
                </div>
              )}

              {/* Errors */}
              {error && (
                <div style={{ padding: '10px 14px', borderRadius: '6px', background: '#fee2e2', border: '1px solid #dc2626', display: 'flex', alignItems: 'center', gap: '8px', color: '#991b1b' }}>
                  <AlertCircle size={16} />
                  <span style={{ fontSize: '12px', fontWeight: 600 }}>{error}</span>
                </div>
              )}

              {/* Submit */}
              <button 
                type="submit" 
                className="btn-vintage"
                disabled={loading || !title.trim() || (inputMode === 'file' ? !selectedFile : !rawText.trim())}
              >
                {loading ? (
                  <>
                    <Loader className="shimmer-text" style={{ animation: 'spin 1s linear infinite' }} size={16} />
                    Extracting Manuscript...
                  </>
                ) : (
                  <>
                    <Edit3 size={16} />
                    Prepare Manuscript Grid
                  </>
                )}
              </button>

            </form>
          </div>
        ) : (
          
          /* State B: Lined Pages Preview Editor */
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            
            {/* Header controls */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px dashed rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
              <div>
                <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#f3f4f6' }}>Manuscript Pages Editor</h3>
                <p style={{ fontSize: '12px', color: 'var(--text-muted-light)' }}>
                  Each sheet is a document page. Highlight text and click "Crop Selection" to keep only that portion.
                </p>
              </div>
              <button 
                className="btn-retry-vintage"
                onClick={() => setIsEditingPreviews(false)}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', borderColor: 'rgba(255,255,255,0.3)', color: '#fff' }}
              >
                <X size={12} />
                Cancel
              </button>
            </div>

            {/* Stacked Pages container */}
            <div className="corkboard">
              {previewPages.map((page, idx) => (
                <div 
                  key={page.id}
                  className="manuscript-sheet"
                >
                  <div className="sheet-header">
                    <span className="sheet-num">
                      <FileText size={14} color="#856b3e" />
                      Page {page.pageNum}
                    </span>
                  </div>

                  {page.is_comic && page.image_url ? (
                    <div style={{ padding: '10px', display: 'flex', flexDirection: 'column', alignItems: 'center', background: '#fcfaf2', borderRadius: '4px', border: '1px dashed #d1c7ac', margin: '10px 0' }}>
                      <img 
                        src={page.image_url} 
                        alt={`Comic page ${page.pageNum}`} 
                        style={{ maxWidth: '100%', maxHeight: '350px', borderRadius: '4px', objectFit: 'contain', boxShadow: '0 4px 10px rgba(0,0,0,0.15)' }} 
                      />
                      <span style={{ fontSize: '11px', color: '#8a7e72', marginTop: '8px', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>
                        Manga Image Page extracted from PDF.
                      </span>
                    </div>
                  ) : (
                    <textarea
                      id={`textarea-${page.id}`}
                      className="sheet-textarea"
                      value={page.text}
                      onChange={(e) => handlePageTextChange(page.id, e.target.value)}
                    />
                  )}

                  <div className="sheet-actions">
                    {!page.is_comic && (
                      <button 
                        className="btn-sheet-action crop"
                        onClick={() => handleCropPage(page.id)}
                        title="Keep only the highlighted selection"
                      >
                        <Sparkles size={12} />
                        Crop Selection
                      </button>
                    )}
                    <button 
                      className="btn-sheet-action delete"
                      onClick={() => handleDeletePage(page.id)}
                      title="Remove this entire page"
                    >
                      <Trash2 size={12} />
                      Delete Page
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Errors in preview state */}
            {error && (
              <div style={{ padding: '10px 14px', borderRadius: '6px', background: '#fee2e2', border: '1px solid #dc2626', display: 'flex', alignItems: 'center', gap: '8px', color: '#991b1b' }}>
                <AlertCircle size={16} />
                <span style={{ fontSize: '12px', fontWeight: 600 }}>{error}</span>
              </div>
            )}

            {/* Compilation buttons */}
            <div style={{ display: 'flex', gap: '16px', marginTop: '8px' }}>
              <button
                className="btn-vintage"
                style={{ flex: 1, background: 'linear-gradient(135deg, #10b981, #047857)', borderColor: 'rgba(255,255,255,0.15)' }}
                onClick={handleCompileManhwa}
                disabled={loading || previewPages.length === 0}
              >
                {loading ? (
                  <>
                    <Loader className="shimmer-text" style={{ animation: 'spin 1s linear infinite' }} size={16} />
                    {previewPages.some(p => p.is_comic) ? "Processing Manga Chapters..." : "Compiling & Queueing AI Panels..."}
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    {previewPages.some(p => p.is_comic) ? `Assemble ${previewPages.length} Comic Pages` : `Compile ${previewPages.length} Pages to Manhwa`}
                  </>
                )}
              </button>
            </div>

          </div>
        )}

      </div>

    </div>
  )
}

export default UploadView
