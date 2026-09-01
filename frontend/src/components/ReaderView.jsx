import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { ArrowLeft, RefreshCw, AlertCircle, Wand2, Battery, Wifi, Maximize2, Minimize2, BookOpen } from 'lucide-react'

const API_BASE = 'http://localhost:8000'

// Helper to extract non-dialogue narration text from a paragraph
const getNarrationText = (scene) => {
  if (!scene.paragraph_text) return null;
  if (scene.paragraph_text.includes("Comic Page") || scene.paragraph_text.includes("Manhwa Page") || scene.paragraph_text.startsWith("[")) {
    return null;
  }
  // Remove direct speech quotes (supports standard and curly quotes)
  const textWithoutQuotes = scene.paragraph_text.replace(/"[^"]*"/g, '').replace(/“[^”]*”/g, '').trim();
  
  if (textWithoutQuotes.length > 0) {
    // Take the first sentence
    const firstSentence = textWithoutQuotes.split(/[.!?]/)[0].trim();
    if (firstSentence.length > 3) {
      let cleaned = firstSentence.replace(/^[,.\s]+/, '').trim();
      
      // Filter out simple dialogue speech attributions (e.g. "Elena asked", "she said softly")
      const lowerCleaned = cleaned.toLowerCase();
      const attributionVerbs = ['said', 'asked', 'thought', 'replied', 'whispered', 'shouted', 'yelled', 'cried', 'says', 'asks', 'murmured', 'muttered', 'explained', 'told', 'replies'];
      const isAttribution = cleaned.length < 25 && attributionVerbs.some(verb => lowerCleaned.includes(verb));
      
      if (cleaned.length > 0 && !isAttribution) {
        return cleaned.charAt(0).toUpperCase() + cleaned.slice(1) + "...";
      }
    }
  }
  return null;
};

function ReaderView({ chapterId, onBack }) {
  const [scenes, setScenes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeIndex, setActiveIndex] = useState(null)
  const [ribbonTop, setRibbonTop] = useState(0)
  const [isFullComic, setIsFullComic] = useState(false)
  
  const [progress, setProgress] = useState({
    total: 0,
    completed: 0,
    percentage: 0
  })

  // Poll intervals reference
  const pollIntervalRef = useRef(null)

  // Fetch scenes
  const fetchScenes = async (showLoader = false) => {
    if (showLoader) setLoading(true)
    try {
      const response = await axios.get(`${API_BASE}/api/chapters/${chapterId}/scenes`)
      setScenes(response.data || [])
      
      // Fetch progress
      const statusRes = await axios.get(`${API_BASE}/api/chapters/${chapterId}/status`)
      setProgress(statusRes.data)
      
      setError(null)
    } catch (err) {
      console.error('Error fetching scenes:', err)
      setError('Failed to fetch scenes from backend.')
    } finally {
      if (showLoader) setLoading(false)
    }
  }

  // Initial Fetch & Poll setups
  useEffect(() => {
    fetchScenes(true)
    
    // Poll every 3 seconds
    pollIntervalRef.current = setInterval(() => {
      fetchScenes(false)
    }, 3000)

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    }
  }, [chapterId])

  // Stop polling if everything is completed or failed
  useEffect(() => {
    if (scenes.length > 0) {
      const activeTasks = scenes.some(
        s => s.status === 'pending' || s.status === 'generating'
      )
      if (!activeTasks && pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
        console.log('Pipeline finished processing all scenes. Stopping polling.')
      }
    }
  }, [scenes])

  // Set up Intersection Observer for Left Pane (Book Pane) scrolling
  useEffect(() => {
    if (scenes.length === 0) return

    const scrollPane = document.querySelector('.book-pane')
    if (!scrollPane) return

    // Intersection observer setup
    const observerOptions = {
      root: scrollPane,
      rootMargin: '-30% 0px -40% 0px', // Center focus
      threshold: 0.1
    }

    const observerCallback = (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const index = parseInt(entry.target.getAttribute('data-index'), 10)
          setActiveIndex(index)
        }
      })
    }

    const observer = new IntersectionObserver(observerCallback, observerOptions)
    
    // Observe paragraphs
    const elements = document.querySelectorAll('.book-paragraph')
    elements.forEach(el => observer.observe(el))

    return () => observer.disconnect()
  }, [scenes])

  // Track and align the Ribbon Bookmark next to the active paragraph
  useEffect(() => {
    if (activeIndex === null) return
    const activeEl = document.querySelector(`.book-paragraph[data-index="${activeIndex}"]`)
    if (activeEl) {
      // Calculate top relative position of paragraph
      setRibbonTop(activeEl.offsetTop + 12)
    }

    // Scroll corresponding manhwa panel in smartphone into view
    const panel = document.getElementById(`manhwa-panel-${activeIndex}`)
    if (panel) {
      panel.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      })
    }
  }, [activeIndex])

  // Handle retry click for failed scene
  const handleRetryScene = async (sceneId, index) => {
    // Optimistic status update
    setScenes(prev => {
      const updated = [...prev]
      updated[index] = { ...updated[index], status: 'pending', error_message: null }
      return updated
    })

    try {
      await axios.post(`${API_BASE}/api/scenes/${sceneId}/retry`)
      // Restart polling if it was stopped
      if (!pollIntervalRef.current) {
        pollIntervalRef.current = setInterval(() => {
          fetchScenes(false)
        }, 3000)
      }
    } catch (err) {
      console.error('Failed to retry scene:', err)
      setError('Retry trigger failed. Please check backend connection.')
    }
  }

  // Handle manual left paragraph click to trigger alignment
  const handleParagraphClick = (index) => {
    setActiveIndex(index)
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '80vh', gap: '16px' }}>
        <RefreshCw className="shimmer-text" style={{ animation: 'spin 2s linear infinite' }} size={40} color="var(--primary-purple)" />
        <p style={{ color: 'var(--text-muted-light)', fontFamily: 'var(--font-display)' }}>Formatting E-Book Manuscript...</p>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 84px)', overflow: 'hidden' }}>
      
      {/* Reader Status Bar */}
      <div className="glass-panel" style={{
        margin: '0 16px 12px 16px',
        padding: '10px 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderRadius: '10px',
        background: 'hsla(225, 20%, 8%, 0.4)',
        borderColor: 'rgba(255,255,255,0.05)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
          <Wand2 size={16} color="var(--primary-purple)" />
          <span style={{ fontSize: '13px', color: 'var(--text-muted-light)', fontWeight: 500 }}>
            Compiled: {progress.completed} / {progress.total} Panels
          </span>
          <div style={{ flex: 1, maxWidth: '250px', height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden', margin: '0 8px' }}>
            <div style={{
              width: `${progress.percentage}%`,
              height: '100%',
              background: 'linear-gradient(90deg, var(--primary-purple), #d946ef)',
              transition: 'width 0.5s ease'
            }}></div>
          </div>
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--primary-purple)' }}>
            {progress.percentage}%
          </span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {progress.percentage < 100 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#a78bfa', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginRight: '8px' }}>
              <RefreshCw size={12} className="shimmer-text" style={{ animation: 'spin 2s linear infinite' }} />
              Drawing in studio...
            </div>
          )}
          
          <button 
            onClick={() => setIsFullComic(!isFullComic)}
            className="btn-retry-vintage"
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '6px', 
              borderColor: 'rgba(167, 139, 250, 0.4)', 
              color: '#fff', 
              padding: '6px 12px',
              fontSize: '11px',
              fontFamily: 'var(--font-serif)',
              cursor: 'pointer'
            }}
          >
            {isFullComic ? <BookOpen size={12} /> : <Maximize2 size={12} />}
            {isFullComic ? "Split Book View" : "Full Screen Comic"}
          </button>
        </div>
      </div>

      {/* Reader Layout Grid */}
      <div className={`reader-container ${isFullComic ? 'full-comic-mode' : ''}`}>
        
        {/* LEFT PANE - Physical Book Page */}
        <div className="book-pane">
          {/* Moving Silk Ribbon Bookmark */}
          <div 
            className="bookmark-ribbon" 
            style={{ 
              transform: `translateY(${ribbonTop}px)`,
              height: '40px' /* Bookmark tab size */
            }}
          ></div>
          
          {scenes.map((scene, idx) => (
            <div 
              key={scene.id}
              className={`book-paragraph ${activeIndex === idx ? 'active' : ''}`}
              data-index={idx}
              onClick={() => handleParagraphClick(idx)}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                <span style={{ 
                  fontSize: '11px', 
                  fontFamily: 'var(--font-mono)', 
                  background: activeIndex === idx ? 'var(--accent-ribbon)' : 'rgba(0,0,0,0.05)',
                  color: activeIndex === idx ? '#fff' : '#8a7e72',
                  borderRadius: '4px',
                  padding: '2px 6px',
                  marginTop: '4px'
                }}>
                  {idx + 1}
                </span>
                <p style={{ flex: 1 }}>{scene.paragraph_text}</p>
              </div>
            </div>
          ))}
        </div>

        {/* RIGHT PANE - Continuous Webtoon Stream */}
        <div className="device-pane">
          <div className="webtoon-stream-container">
            {scenes.map((scene, idx) => (
              <div 
                key={scene.id}
                id={`manhwa-panel-${idx}`}
                className={`manhwa-card ${activeIndex === idx ? 'active-panel' : ''}`}
              >
                {/* Completed Panel */}
                {scene.status === 'completed' && (
                  <div className="manhwa-card-container">
                    <img 
                      src={scene.image_url} 
                      alt={`Manhwa scene ${idx + 1}`} 
                      className="manhwa-image"
                      loading="lazy"
                    />
                    
                    {/* Comic Speech Balloons & Narration Overlays */}
                    <div className="comic-overlays-container">
                      
                      {/* Narration box at the top corner (extracts story description instead of AI prompts) */}
                      {(() => {
                        const narrationText = getNarrationText(scene);
                        return narrationText ? (
                          <div className="comic-narration">
                            <span className="comic-narration-text">{narrationText}</span>
                          </div>
                        ) : null;
                      })()}
                      
                      {/* Dialogue Bubbles overlay */}
                      {scene.dialogue ? (
                        (() => {
                          const dialogueList = scene.dialogue.split(' | ').map(d => d.trim()).filter(d => d.length > 0)
                          return dialogueList.map((dialogueText, dialIdx) => {
                            // Alternate bubble placement
                            const isLeft = (idx + dialIdx) % 2 === 0
                            const posClass = isLeft ? 'bubble-pos-left' : 'bubble-pos-right'
                            const tailClass = isLeft ? 'bubble-tail-left' : 'bubble-tail-right'
                            
                            // Translate second bubble down slightly to prevent overlaps
                            const bubbleStyle = dialIdx > 0 ? { transform: 'translateY(16px)' } : {}
                            
                            return (
                              <div 
                                key={dialIdx}
                                className={`comic-bubble ${posClass} ${tailClass}`}
                                style={bubbleStyle}
                              >
                                <span className="comic-bubble-text">{dialogueText}</span>
                              </div>
                            )
                          })
                        })()
                      ) : null}
                    </div>
                  </div>
                )}

                {/* Pending / Generating Panel Shimmers */}
                {(scene.status === 'pending' || scene.status === 'generating') && (
                  <div className="shimmer">
                    <Wand2 size={24} color="var(--primary-purple)" style={{ animation: 'pulse 1.5s infinite' }} />
                    <span className="shimmer-text">
                      {scene.status === 'generating' ? 'Drawing...' : 'Queued...'}
                    </span>
                    {scene.image_prompt && (
                      <p style={{ 
                        fontSize: '9px', 
                        color: '#6b7280', 
                        padding: '0 16px', 
                        textAlign: 'center',
                        lineHeight: 1.3,
                        marginTop: '4px'
                      }}>
                        Scripting: "{scene.image_prompt.substring(0, 50)}..."
                      </p>
                    )}
                  </div>
                )}

                {/* Failed Panel View */}
                {scene.status === 'failed' && (
                  <div className="error-panel">
                    <AlertCircle size={24} color="#ef4444" />
                    <span style={{ fontSize: '12px', fontWeight: 700 }}>Failed panel</span>
                    <button 
                      onClick={() => handleRetryScene(scene.id, idx)}
                      className="btn-retry-vintage"
                    >
                      Retry
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}

export default ReaderView
