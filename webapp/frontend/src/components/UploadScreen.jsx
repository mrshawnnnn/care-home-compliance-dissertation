import { useState, useRef } from 'react';

export default function UploadScreen({ onSubmit, error }) {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const acceptedTypes = ['.pdf', '.docx', '.txt'];

  function handleFiles(fileList) {
    const f = fileList[0];
    if (!f) return;
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!acceptedTypes.includes(ext)) {
      return;
    }
    setFile(f);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }

  return (
    <div className="intake-card">
      <h1 className="intake-heading">Compliance Check</h1>
      <p className="intake-sub">
        Upload an IT policy, training record, or incident log. Each statement
        is checked against Cyber Essentials and DSPT requirements, sentence
        by sentence.
      </p>

      <div
        className={`dropzone ${dragging ? 'dragging' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter') inputRef.current?.click(); }}
      >
        <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 16V4M12 4L7 9M12 4l5 5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <div className="dropzone-label">
          {file ? 'Choose a different file' : 'Drop a document here, or click to browse'}
        </div>
        <div className="dropzone-hint">PDF, Word (.docx), or plain text — up to 400 sentences</div>
        <input
          ref={inputRef}
          type="file"
          className="file-input-hidden"
          accept={acceptedTypes.join(',')}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {file && (
        <div className="selected-file">
          <span>{file.name}</span>
          <span>·</span>
          <span>{(file.size / 1024).toFixed(0)} KB</span>
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}

      <button
        className="btn-primary"
        disabled={!file}
        onClick={() => onSubmit(file)}
      >
        Check this document
      </button>
    </div>
  );
}
