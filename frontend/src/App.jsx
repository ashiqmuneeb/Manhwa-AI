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
      {/* Real-World Studio Executive Console Header */}
      <header style={{
        margin: '16px 24px',
        padding: '14px 28px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderRadius: '10px',
        background: 'linear-gradient(180deg, #242226 0%, #161518 100%)',
        border: '1.5px solid #3d3b42',
        boxShadow: '0 10px 28px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,255,255,0.15)',
        position: 'relative',
        zIndex: 50
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', cursor: 'pointer' }} onClick={handleReturnToUpload}>
          <div style={{
            background: 'linear-gradient(135deg, #8b5cf6 0%, #4f46e5 100%)',
            padding: '10px',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 18px rgba(139, 92, 246, 0.4), inset 0 1px 0 rgba(255,255,255,0.4)',
            border: '1px solid #c084fc'
          }}>
            <BookOpen size={22} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: '19px', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '8px', letterSpacing: '-0.02em', color: '#f3f4f6' }}>
              MANHWA AI <span style={{ 
                fontSize: '10px', 
                background: 'rgba(139, 92, 246, 0.2)', 
                padding: '2px 8px', 
                borderRadius: '4px',
                color: '#c4b5fd',
                fontWeight: 700,
                border: '1px solid rgba(139, 92, 246, 0.4)',
                letterSpacing: '0.05em'
              }}>STUDIO v2.0</span>
            </h1>
            <span style={{ fontSize: '11px', color: '#9ca3af', fontWeight: 500, letterSpacing: '0.04em' }}>
              Full-Story Semantic Director & Action Webtoon Engine
            </span>
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
