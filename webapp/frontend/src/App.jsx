import { useState, useEffect, useCallback } from 'react';
import UploadScreen from './components/UploadScreen';
import AnalyzingScreen from './components/AnalyzingScreen';
import ReportScreen from './components/ReportScreen';

const API_BASE = 'http://localhost:8000';

// idle -> analyzing -> report | error
export default function App() {
  const [screen, setScreen] = useState('idle');
  const [error, setError] = useState(null);
  const [health, setHealth] = useState(null);
  const [fileName, setFileName] = useState('');

  const [total, setTotal] = useState(0);
  const [current, setCurrent] = useState(0);
  const [feed, setFeed] = useState([]);
  const [findings, setFindings] = useState([]);
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then(r => r.json())
      .then(setHealth)
      .catch(() => setHealth({ ok: false, message: 'Cannot reach the backend server.' }));
  }, []);

  const reset = useCallback(() => {
    setScreen('idle');
    setError(null);
    setTotal(0);
    setCurrent(0);
    setFeed([]);
    setFindings([]);
    setSummary(null);
  }, []);

  async function handleSubmit(file) {
    setError(null);
    setFileName(file.name);
    setScreen('analyzing');
    setTotal(0);
    setCurrent(0);
    setFeed([]);
    setFindings([]);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Server responded with ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line for next chunk

        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          handleEvent(event);
        }
      }
    } catch (e) {
      setError(e.message || 'Something went wrong while checking the document.');
      setScreen('idle');
    }
  }

  function handleEvent(event) {
    if (event.event === 'extracted') {
      setTotal(event.relevant_count);
      if (event.relevant_count === 0) {
        setError(
          `No compliance-relevant statements were found in this document ` +
          `(checked ${event.total_document_sentences} sentences). Try a ` +
          `document that discusses IT policy, training, or data handling.`
        );
        setScreen('idle');
      }
    } else if (event.event === 'progress') {
      setCurrent(event.index);
      setFeed(prev => [...prev, event.finding].slice(-6)); // keep last 6 visible
      setFindings(prev => [...prev, event.finding]);
    } else if (event.event === 'done') {
      setSummary(event.summary);
      setScreen('report');
    } else if (event.event === 'error') {
      setError(event.message);
      setScreen('idle');
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <div className="app-title">Compliance Check</div>
          <div className="app-tagline">Cyber Essentials &amp; DSPT — automated, local, sentence-level</div>
        </div>
        {health && (
          <span className={`status-pill ${health.ok ? 'ok' : 'down'}`}>
            {health.ok ? 'Model ready' : 'Model unavailable'}
          </span>
        )}
      </header>

      <main className="app-main">
        <div className="app-container">
          {screen === 'idle' && (
            <UploadScreen onSubmit={handleSubmit} error={error} />
          )}
          {screen === 'analyzing' && (
            <AnalyzingScreen total={total} current={current} feed={feed} />
          )}
          {screen === 'report' && (
            <ReportScreen
              findings={findings}
              summary={summary}
              fileName={fileName}
              onReset={reset}
            />
          )}
        </div>
      </main>
    </div>
  );
}
