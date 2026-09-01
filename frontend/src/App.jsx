import React, { useState } from 'react'
import UploadView from './components/UploadView'
import ReaderView from './components/ReaderView'
import { Sparkles, BookOpen } from 'lucide-react'

function App() {
  const [viewState, setViewState] = useState('upload') // 'upload' | 'reader'
  const [chapterId, setChapterId] = useState(null)
  const [novelTitle, setNovelTitle] = useState('My Web Novel')

  const handleUploadSuccess = (data) => {
    setChapterId(data.chapter_id)
    setNovelTitle(data.title || 'My Web Novel')
    setViewState('reader')
  }

  const handleReturnToUpload = () => {
    setViewState('upload')
    setChapterId(null)
  }

  return (
    <div className="app-root" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Navigation Header */}
      <header className="glass-panel" style={{
        margin: '16px',
        padding: '12px 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderRadius: '12px',
        zIndex: 50,
        background: 'hsla(225, 20%, 10%, 0.7)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }} onClick={handleReturnToUpload}>
          <div style={{
            background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
            padding: '8px',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px var(--primary-glow)'
          }}>
            <BookOpen size={20} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: '18px', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
              ManhwaAI <span style={{ 
                fontSize: '11px', 
                background: 'rgba(255,255,255,0.08)', 
                padding: '2px 6px', 
                borderRadius: '4px',
                color: 'var(--accent-blue)',
                border: '1px solid rgba(255,255,255,0.1)'
              }}>v1.0</span>
            </h1>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Novel to Comic Engine</span>
          </div>
        </div>

        {viewState === 'reader' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <span style={{ 
              fontSize: '14px', 
              color: 'var(--text-secondary)', 
              fontWeight: 500,
              maxWidth: '200px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}>
              📖 {novelTitle}
            </span>
            <button 
              className="btn-retry" 
              onClick={handleReturnToUpload}
              style={{ fontSize: '12px', padding: '6px 12px' }}
            >
              Upload New
            </button>
          </div>
        )}
      </header>

      {/* Main View Container */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {viewState === 'upload' ? (
          <UploadView onUploadSuccess={handleUploadSuccess} />
        ) : (
          <ReaderView chapterId={chapterId} onBack={handleReturnToUpload} />
        )}
      </main>
    </div>
  )
}

export default App
