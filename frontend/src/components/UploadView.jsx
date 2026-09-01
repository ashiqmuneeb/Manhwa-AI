import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { 
  FileText, Sparkles, AlertCircle, Loader, Type, Upload, 
  BookOpen, Trash2, Edit3, X, Check, Film, Wand2, 
  Palette, User, MessageSquare, ArrowRight, ArrowLeft 
} from 'lucide-react'

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

  // AI Director Studio state
  const [isDirectorStudioActive, setIsDirectorStudioActive] = useState(false)
  const [storyAnalysis, setStoryAnalysis] = useState(null)
  const [continuousStoryText, setContinuousStoryText] = useState('')
  const [castList, setCastList] = useState([])
  const [selectedArtStyle, setSelectedArtStyle] = useState('Action Inking with Motion Streaks')
  const [directorAnswers, setDirectorAnswers] = useState({
    action_intensity: 'High-Octane Action (Maximum Speed Lines & Explosive SFX)',
    lighting_palette: 'High-Contrast Night Lighting with Rim Lights'
  })

  const fileInputRef = useRef(null)

  // Fetch Existing Shelf on Mount
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

  // Handle File Selection
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
      
      if (!title) {
        const cleanName = file.name.replace(/\.[^/.]+$/, "")
        setTitle(cleanName)
      }
    }
  }

  // 1. Trigger Full Story Semantic Analysis with Gemini
  const handleAnalyzeStory = async (e) => {
    if (e) e.preventDefault()
    if (!title.trim()) {
      setError('Please enter a story title.')
      return
    }
    if (inputMode === 'file' && !selectedFile) {
      setError('Please select a novel file to analyze.')
      return
    }
    if (inputMode === 'text' && !rawText.trim()) {
      setError('Please enter or paste your story text.')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      if (inputMode === 'file') {
        formData.append('file', selectedFile)
      } else {
        formData.append('raw_text', rawText.trim())
      }

      const response = await axios.post(`${API_BASE}/api/story/analyze-full`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      if (response.data && response.data.success) {
        const data = response.data.data
        setStoryAnalysis(data)
        setContinuousStoryText(data.raw_text || rawText || '')
        
        // Populate character list
        const initialCast = (data.characters || []).map((char, idx) => ({
          id: idx + 1,
          name: char.name || `Character ${idx + 1}`,
          role: char.role || 'Supporting',
          hair: char.hair || '',
          eyes: char.eyes || '',
          clothing: char.clothing || '',
          signature_trait: char.signature_trait || ''
        }))
        setCastList(initialCast.length > 0 ? initialCast : [
          { id: 1, name: 'Elena', role: 'Protagonist', hair: 'Golden blonde', eyes: 'Sapphire blue', clothing: 'Evening gown', signature_trait: 'Antique diary' },
          { id: 2, name: 'Stefan', role: 'Lead', hair: 'Dark wavy', eyes: 'Piercing green', clothing: 'Dark jacket', signature_trait: 'Lapis lazuli ring' }
        ])

        if (data.recommended_art_style) {
          setSelectedArtStyle(data.recommended_art_style)
        }

        // Initialize director answers from questions
        if (data.director_questions) {
          const initialAnswers = {}
          data.director_questions.forEach(q => {
            initialAnswers[q.id] = q.default || q.options[0]
          })
          setDirectorAnswers(initialAnswers)
        }

        setIsDirectorStudioActive(true)
      } else {
        throw new Error('Analysis failed.')
      }
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || err.message || 'Failed to analyze story.')
    } finally {
      setLoading(false)
    }
  }

  // Character Cast Actions
  const handleAddCharacter = () => {
    setCastList(prev => [
      ...prev, 
      { id: Date.now(), name: '', role: 'Character', hair: '', eyes: '', clothing: '', signature_trait: '' }
    ])
  }

  const handleRemoveCharacter = (id) => {
    setCastList(prev => prev.filter(c => c.id !== id))
  }

  const handleUpdateCharacter = (id, field, val) => {
    setCastList(prev => prev.map(c => c.id === id ? { ...c, [field]: val } : c))
  }

  // 2. Final Submission: Compile Manhwa Webtoon
  const handleCompileManhwa = async () => {
    const storyToCompile = continuousStoryText.trim()
    if (!storyToCompile) {
      setError('Story manuscript cannot be empty.')
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Build cast profiles summary string
      const castProfilesStr = castList
        .filter(c => c.name.trim())
        .map(c => `${c.name.trim()} (${c.role}): hair=${c.hair}, eyes=${c.eyes}, outfit=${c.clothing}, accessory=${c.signature_trait}`)
        .join(' | ')

      const formData = new FormData()
      formData.append('title', title.trim())
      formData.append('raw_text', storyToCompile)
      formData.append('max_chapters', maxPages)
      if (castProfilesStr) {
        formData.append('cast_profiles', castProfilesStr)
      }

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
      setError(err.response?.data?.detail || 'Failed to compile manhwa.')
    } finally {
      setLoading(false)
    }
  }

  // Delete novel from shelf
  const handleDeleteNovel = async (e, novelId) => {
    e.stopPropagation()
    if (!window.confirm("Are you sure you want to delete this novel manuscript? This will remove all generated comic panels.")) return

    try {
      await axios.delete(`${API_BASE}/api/novels/${novelId}`)
      fetchNovels()
    } catch (err) {
      console.error('Delete novel failed:', err)
      alert('Failed to delete novel.')
    }
  }

  const handleOpenNovel = (novel) => {
    if (novel.chapters && novel.chapters.length > 0) {
      onUploadSuccess({
        chapter_id: novel.chapters[0].id,
        title: novel.title
      })
    }
  }

  // Calculate estimated scenes
  const wordCount = continuousStoryText.trim() ? continuousStoryText.trim().split(/\s+/).length : 0
  const estimatedPanels = Math.max(5, Math.min(45, Math.ceil(wordCount / 40)))

  return (
    <div className="upload-container">
      <div style={{ maxWidth: '960px', width: '100%', margin: '0 auto' }}>
        
        {/* --- Bookshelf Archive Section (Shown if on Initial Screen) --- */}
        {!isDirectorStudioActive && novels.length > 0 && (
          <div className="bookshelf-container">
            <h3 className="bookshelf-title">
              <BookOpen size={18} color="#ebd4a0" />
              Compiled Manhwa Library ({novels.length})
            </h3>
            
            <div className="bookshelf-grid">
              {novels.map((novel) => {
                const chapterCount = novel.chapters ? novel.chapters.length : 0
                return (
                  <div 
                    key={novel.id} 
                    className="novel-book-card"
                    onClick={() => handleOpenNovel(novel)}
                  >
                    <button 
                      className="novel-card-trash-btn"
                      onClick={(e) => handleDeleteNovel(e, novel.id)}
                      title="Delete novel and panels"
                    >
                      <Trash2 size={13} />
                    </button>
                    
                    <div className="novel-book-spine" />
                    <div className="novel-book-cover">
                      <h4 className="novel-cover-title">{novel.title}</h4>
                      <div className="novel-meta-info">
                        <span>{chapterCount} {chapterCount === 1 ? 'Chapter' : 'Chapters'}</span>
                        <span>•</span>
                        <span>{new Date(novel.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* --- MAIN CARD --- */}
        {!isDirectorStudioActive ? (

          /* =========================================================
             STAGE 1: STORY INPUT & AI DIRECTOR LAUNCH
             ========================================================= */
          <div className="manila-folder-card">
            
            <div className="manila-tab">
              <Sparkles size={14} color="#856b3e" />
              <span>Full-Story AI Director Studio</span>
            </div>

            <div style={{ marginBottom: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '26px', fontWeight: 800, color: '#1c1917', letterSpacing: '-0.01em' }}>
                  Webtoon Storyboard Director
                </h2>
                <span style={{
                  background: '#dc2626',
                  color: '#ffffff',
                  fontSize: '10px',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '4px',
                  letterSpacing: '0.1em',
                  boxShadow: '0 2px 4px rgba(220, 38, 38, 0.4)'
                }}>
                  DOSSIER DRAFT
                </span>
              </div>
              <p style={{ fontSize: '13.5px', color: '#574130', marginTop: '6px', lineHeight: '1.5', fontWeight: 500 }}>
                The AI Story Director will read your entire manuscript, detect character appearances, and ask you visual styling questions before generating your full webtoon comic.
              </p>
            </div>

            <form onSubmit={handleAnalyzeStory} style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
              
              {/* Manuscript Title */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <label style={{ fontSize: '12px', fontWeight: 800, color: '#78350f', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  Manuscript Title // Project Identifier
                </label>
                <input 
                  type="text" 
                  placeholder="e.g. Vampire Diaries, Shadow Martial Arts, Seoul City Fighters..."
                  className="vintage-input"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  disabled={loading}
                />
              </div>

              {/* Mode Toggles */}
              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => setInputMode('file')}
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: '12px 16px',
                    borderRadius: '8px',
                    border: inputMode === 'file' ? '2px solid #7c2d12' : '1.5px solid #c9b180',
                    background: inputMode === 'file' ? '#ffffff' : 'rgba(255,255,255,0.4)',
                    fontFamily: 'var(--font-sans)',
                    fontWeight: 700,
                    fontSize: '13px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    color: inputMode === 'file' ? '#7c2d12' : '#574130',
                    boxShadow: inputMode === 'file' ? '0 4px 10px rgba(124, 45, 18, 0.15)' : 'none',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <Upload size={16} />
                  Upload Novel File (.txt / .pdf)
                </button>
                <button
                  type="button"
                  onClick={() => setInputMode('text')}
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: '12px 16px',
                    borderRadius: '8px',
                    border: inputMode === 'text' ? '2px solid #7c2d12' : '1.5px solid #c9b180',
                    background: inputMode === 'text' ? '#ffffff' : 'rgba(255,255,255,0.4)',
                    fontFamily: 'var(--font-sans)',
                    fontWeight: 700,
                    fontSize: '13px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    color: inputMode === 'text' ? '#7c2d12' : '#574130',
                    boxShadow: inputMode === 'text' ? '0 4px 10px rgba(124, 45, 18, 0.15)' : 'none',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <Type size={16} />
                  Paste Full Text Direct
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
                    <FileText size={32} color="#856b3e" style={{ opacity: 0.8 }} />
                    <div>
                      {selectedFile ? (
                        <p style={{ fontSize: '14px', fontWeight: 700, color: '#3b2f15' }}>
                          Selected File: {selectedFile.name}
                        </p>
                      ) : (
                        <p style={{ fontSize: '14px', fontWeight: 600 }}>
                          Drop manuscript document here or click to browse
                        </p>
                      )}
                      <p style={{ fontSize: '11px', opacity: 0.7, marginTop: '2px' }}>
                        Supports TXT, PDF, and Markdown novel files
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Direct Text Area */}
              {inputMode === 'text' && (
                <div style={{ border: '1px solid rgba(110, 100, 90, 0.2)', borderRadius: '6px', padding: '16px', background: 'rgba(255,255,255,0.2)' }}>
                  <textarea 
                    placeholder="Paste your full novel story here..."
                    className="typewriter-textarea"
                    style={{ minHeight: '220px' }}
                    value={rawText}
                    onChange={(e) => setRawText(e.target.value)}
                    disabled={loading}
                  />
                </div>
              )}

              {/* Error Banner */}
              {error && (
                <div style={{ padding: '10px 14px', borderRadius: '6px', background: '#fee2e2', border: '1px solid #dc2626', display: 'flex', alignItems: 'center', gap: '8px', color: '#991b1b' }}>
                  <AlertCircle size={16} />
                  <span style={{ fontSize: '12px', fontWeight: 600 }}>{error}</span>
                </div>
              )}

              {/* Action Button */}
              <button 
                type="submit" 
                className="btn-vintage"
                style={{ padding: '14px 20px', fontSize: '14px' }}
                disabled={loading || !title.trim() || (inputMode === 'file' ? !selectedFile : !rawText.trim())}
              >
                {loading ? (
                  <>
                    <Loader className="shimmer-text" style={{ animation: 'spin 1s linear infinite' }} size={16} />
                    AI Director is Reading & Analyzing Story...
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    Analyze Story with AI Director
                    <ArrowRight size={16} />
                  </>
                )}
              </button>

            </form>
          </div>

        ) : (

          /* =========================================================
             STAGE 2: INTERACTIVE AI DIRECTOR & SINGLE-PAGE STUDIO
             ========================================================= */
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            
            {/* Top Navigation Bar */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.05)', padding: '12px 18px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
              <button
                onClick={() => setIsDirectorStudioActive(false)}
                style={{
                  background: 'transparent',
                  border: '1px solid rgba(255,255,255,0.2)',
                  borderRadius: '6px',
                  color: '#e5e7eb',
                  padding: '6px 12px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <ArrowLeft size={14} />
                Back to Story Input
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '12px', color: '#a78bfa', fontWeight: 600 }}>
                  ⚡ Estimated Panels: ~{estimatedPanels}
                </span>
                <button
                  onClick={handleCompileManhwa}
                  disabled={loading}
                  style={{
                    background: 'linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)',
                    border: 'none',
                    borderRadius: '6px',
                    color: '#fff',
                    padding: '8px 18px',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    boxShadow: '0 4px 14px rgba(124, 58, 237, 0.4)'
                  }}
                >
                  {loading ? (
                    <>
                      <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} />
                      Compiling Webtoon...
                    </>
                  ) : (
                    <>
                      <Wand2 size={14} />
                      Compile Webtoon Comic
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* AI Synopsis & Genre Card */}
            {storyAnalysis && (
              <div style={{
                background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%)',
                border: '1px solid rgba(139, 92, 246, 0.3)',
                borderRadius: '10px',
                padding: '18px 22px',
                boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Film size={16} color="#a78bfa" />
                    <span style={{ fontSize: '14px', fontWeight: 800, color: '#f3f4f6', letterSpacing: '0.05em' }}>
                      AI STORY DIRECTING REPORT: {title}
                    </span>
                  </div>
                  <span style={{
                    background: 'rgba(139, 92, 246, 0.25)',
                    color: '#c4b5fd',
                    padding: '3px 10px',
                    borderRadius: '12px',
                    fontSize: '11px',
                    fontWeight: 700,
                    border: '1px solid rgba(139, 92, 246, 0.4)'
                  }}>
                    {storyAnalysis.genre_and_tone || 'Action Webtoon'}
                  </span>
                </div>
                
                <p style={{ fontSize: '13px', color: '#d1d5db', lineHeight: '1.5' }}>
                  {storyAnalysis.synopsis}
                </p>
              </div>
            )}

            {/* --- CHARACTER CAST VISUAL IDENTITY STUDIO --- */}
            <div style={{
              background: '#18181b',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '10px',
              padding: '20px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '10px' }}>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f3f4f6', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <User size={16} color="#38bdf8" />
                    Character Visual Cast Sheet (Identity Locking)
                  </h3>
                  <p style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
                    The AI will lock these exact features for every character across all 30+ comic panels.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleAddCharacter}
                  style={{
                    background: 'rgba(56, 189, 248, 0.15)',
                    border: '1px solid rgba(56, 189, 248, 0.4)',
                    color: '#38bdf8',
                    borderRadius: '6px',
                    padding: '4px 10px',
                    fontSize: '11px',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  + Add New Character
                </button>
              </div>

              {/* Character Cards Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '14px' }}>
                {castList.map((char) => (
                  <div 
                    key={char.id}
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '8px',
                      padding: '14px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '10px',
                      position: 'relative'
                    }}
                  >
                    {castList.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveCharacter(char.id)}
                        style={{
                          position: 'absolute',
                          top: '10px',
                          right: '10px',
                          background: 'transparent',
                          border: 'none',
                          color: '#ef4444',
                          cursor: 'pointer',
                          opacity: 0.8
                        }}
                      >
                        <X size={14} />
                      </button>
                    )}

                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input
                        type="text"
                        placeholder="Character Name"
                        value={char.name}
                        onChange={(e) => handleUpdateCharacter(char.id, 'name', e.target.value)}
                        style={{
                          flex: 1,
                          background: 'rgba(0,0,0,0.4)',
                          border: '1px solid rgba(255,255,255,0.15)',
                          borderRadius: '4px',
                          padding: '6px 8px',
                          fontSize: '13px',
                          fontWeight: 700,
                          color: '#f9fafb'
                        }}
                      />
                      <input
                        type="text"
                        placeholder="Role (Lead / Fighter)"
                        value={char.role}
                        onChange={(e) => handleUpdateCharacter(char.id, 'role', e.target.value)}
                        style={{
                          width: '90px',
                          background: 'rgba(0,0,0,0.4)',
                          border: '1px solid rgba(255,255,255,0.15)',
                          borderRadius: '4px',
                          padding: '6px 8px',
                          fontSize: '11px',
                          color: '#9ca3af'
                        }}
                      />
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px' }}>
                      <div>
                        <span style={{ color: '#9ca3af' }}>Hair & Eyes:</span>
                        <input
                          type="text"
                          placeholder="e.g. Blonde spiky hair, dark intense eyes"
                          value={char.hair ? `${char.hair}${char.eyes ? ', ' + char.eyes : ''}` : (char.appearance || '')}
                          onChange={(e) => handleUpdateCharacter(char.id, 'hair', e.target.value)}
                          style={{
                            width: '100%',
                            background: 'rgba(0,0,0,0.3)',
                            border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: '4px',
                            padding: '4px 6px',
                            color: '#e5e7eb',
                            marginTop: '2px'
                          }}
                        />
                      </div>
                      <div>
                        <span style={{ color: '#9ca3af' }}>Signature Outfit / Accessories:</span>
                        <input
                          type="text"
                          placeholder="e.g. Black leather jacket, silver hoop earrings"
                          value={char.clothing || char.signature_trait || ''}
                          onChange={(e) => handleUpdateCharacter(char.id, 'clothing', e.target.value)}
                          style={{
                            width: '100%',
                            background: 'rgba(0,0,0,0.3)',
                            border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: '4px',
                            padding: '4px 6px',
                            color: '#e5e7eb',
                            marginTop: '2px'
                          }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* --- DIRECTOR AESTHETIC & STYLE QUESTIONNAIRE --- */}
            {storyAnalysis && storyAnalysis.director_questions && (
              <div className="director-studio-card">
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f3f4f6', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Palette size={16} color="#f59e0b" />
                  Director Questionnaire (How do you want it styled?)
                </h3>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
                  {storyAnalysis.director_questions.map((q) => (
                    <div 
                      key={q.id}
                      className="char-card-premium"
                    >
                      <label style={{ fontSize: '12px', fontWeight: 700, color: '#e5e7eb' }}>
                        {q.question}
                      </label>
                      <select
                        value={directorAnswers[q.id] || q.default}
                        onChange={(e) => setDirectorAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                        style={{
                          background: '#09090b',
                          border: '1px solid rgba(255,255,255,0.2)',
                          borderRadius: '6px',
                          padding: '8px 10px',
                          color: '#f3f4f6',
                          fontSize: '12px',
                          cursor: 'pointer'
                        }}
                      >
                        {q.options.map((opt, i) => (
                          <option key={i} value={opt}>{opt}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* --- SINGLE-PAGE UNIFIED STORY PREVIEW CANVAS --- */}
            <div className="director-studio-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f3f4f6', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <FileText size={16} color="#10b981" />
                    Unified Single-Page Storyboard Canvas
                  </h3>
                  <p style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
                    Continuous single-page manuscript. Edit any line or dialogue directly before rendering.
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '10px', fontSize: '11px', color: '#9ca3af' }}>
                  <span>Words: {wordCount}</span>
                  <span>•</span>
                  <span>Estimated Panels: ~{estimatedPanels}</span>
                </div>
              </div>

              {/* Single Continuous Editor */}
              <textarea
                value={continuousStoryText}
                onChange={(e) => setContinuousStoryText(e.target.value)}
                className="single-page-canvas"
                placeholder="Your story text flows continuously here..."
              />

              {/* Bottom Compile Callout */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
                <button
                  onClick={handleCompileManhwa}
                  disabled={loading}
                  style={{
                    background: 'linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)',
                    border: 'none',
                    borderRadius: '8px',
                    color: '#fff',
                    padding: '12px 28px',
                    fontSize: '14px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    boxShadow: '0 4px 16px rgba(124, 58, 237, 0.4)'
                  }}
                >
                  {loading ? (
                    <>
                      <Loader size={16} style={{ animation: 'spin 1s linear infinite' }} />
                      Directing & Generating Panels...
                    </>
                  ) : (
                    <>
                      <Wand2 size={16} />
                      Compile Webtoon Comic (~{estimatedPanels} Panels)
                      <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </div>

            </div>


          </div>
        )}

      </div>
    </div>
  )
}

export default UploadView
