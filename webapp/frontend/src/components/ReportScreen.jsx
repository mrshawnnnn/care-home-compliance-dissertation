import { useState, useMemo } from 'react';

export default function ReportScreen({ findings, summary, fileName, onReset }) {
  const [filter, setFilter] = useState('all'); // all | compliant | noncompliant

  const visible = useMemo(() => {
    if (filter === 'all') return findings;
    if (filter === 'compliant') return findings.filter(f => f.label === 'COMPLIANT');
    return findings.filter(f => f.label === 'NON_COMPLIANT');
  }, [findings, filter]);

  const rate = summary ? Math.round(summary.compliant_rate * 100) : 0;

  return (
    <div>
      <div className="report-stamp">
        <div className="stamp-figure">{rate}%</div>
        <div className="stamp-body">
          <div className="stamp-headline">
            of statements in {fileName} meet the requirements checked
          </div>
          <div className="stamp-counts">
            <span className="compliant">{summary?.compliant_count ?? 0} compliant</span>
            {'  ·  '}
            <span className="noncompliant">{summary?.non_compliant_count ?? 0} flagged</span>
            {summary?.parse_failures > 0 && `  ·  ${summary.parse_failures} unreadable`}
          </div>
        </div>
      </div>

      <div className="report-toolbar">
        <button
          className={`filter-chip ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All ({findings.length})
        </button>
        <button
          className={`filter-chip ${filter === 'noncompliant' ? 'active' : ''}`}
          onClick={() => setFilter('noncompliant')}
        >
          Flagged ({summary?.non_compliant_count ?? 0})
        </button>
        <button
          className={`filter-chip ${filter === 'compliant' ? 'active' : ''}`}
          onClick={() => setFilter('compliant')}
        >
          Compliant ({summary?.compliant_count ?? 0})
        </button>
      </div>

      <div className="findings-list">
        {visible.map((f) => (
          <div
            key={f.index}
            className={`finding ${f.label === 'COMPLIANT' ? 'compliant' : 'noncompliant'}`}
          >
            <span className={`finding-marker ${f.label === 'COMPLIANT' ? 'compliant' : 'noncompliant'}`}>
              {f.label === 'COMPLIANT' ? 'Meets requirement' : 'Needs attention'}
            </span>
            <div className="finding-body">
              <div className="finding-sentence">{f.sentence}</div>
              <div className="finding-meta">{f.control || 'Control not specified'}</div>
              {f.label === 'NON_COMPLIANT' && f.reason && (
                <div className="finding-reason">{f.reason}</div>
              )}
            </div>
          </div>
        ))}
        {visible.length === 0 && (
          <p style={{ color: 'var(--muted)', fontSize: 14 }}>No statements in this view.</p>
        )}
      </div>

      <div className="report-footer">
        <button className="btn-secondary" onClick={onReset}>Check another document</button>
        <p className="disclaimer">
          This is an informational check only and does not replace formal DSPT
          submission or a CQC assessment.
        </p>
      </div>
    </div>
  );
}
