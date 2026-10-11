import { BookOpen, Handshake, Upload } from 'lucide-react'
import { useState } from 'react'
import { FeatureCard } from './components/FeatureCard'
import { isSupabaseConfigured } from './lib/supabase'
import './styles.css'

export default function App() {
  const [message, setMessage] = useState('')

  const showMessage = (text: string) => {
    setMessage(text)
    window.setTimeout(() => setMessage(''), 2600)
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="StudySync home">
          <img src="/assets/logo-mark.png" alt="" className="brand-mark" />
          <span>StudySync</span>
        </a>

        <button
          className="login-button"
          type="button"
          onClick={() => showMessage('Login will be connected in the next implementation step.')}
        >
          Login
        </button>
      </header>

      <main>
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-wave" aria-hidden="true" />
          <div className="hero-content">
            <div className="hero-copy">
              <h1 id="hero-title">StudySync</h1>
              <p>
                Centralized Study Resources.<br />
                Decentralized Student Power.
              </p>
              <div className="hero-actions">
                <button
                  className="primary-button"
                  type="button"
                  onClick={() => showMessage('Resource browsing will be connected next.')}
                >
                  Browse Resources
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => showMessage('Upload and admin approval will be connected next.')}
                >
                  Upload Notes
                </button>
              </div>
            </div>

            <div className="hero-art-wrap">
              <img
                src="/assets/hero-illustration.png"
                alt="Student studying with digital academic resources"
                className="hero-art"
              />
            </div>
          </div>
        </section>

        <section className="features-section" aria-labelledby="features-title">
          <h2 id="features-title">Features</h2>
          <div className="features-grid">
            <FeatureCard
              icon={BookOpen}
              title="Access Quality Notes"
              description="Centralized Study Resources. Decentralized Student Power."
            />
            <FeatureCard
              icon={Upload}
              title="Share & Upload"
              description="Upload notes, resources, and useful materials for fellow students."
              highlighted
            />
            <FeatureCard
              icon={Handshake}
              title="Collaborative Learning"
              description="Discover shared resources and learn together with your peers."
            />
          </div>
        </section>
      </main>

      <footer className="footer">© 2026 StudySync. All rights reserved.</footer>

      {message && (
        <div className="toast" role="status">
          {message}
        </div>
      )}

      {/* This confirms the frontend can load the Supabase client without requiring any tables yet. */}
      <span className="sr-only">
        Supabase connection: {isSupabaseConfigured ? 'configured' : 'not configured'}
      </span>
    </div>
  )
}
