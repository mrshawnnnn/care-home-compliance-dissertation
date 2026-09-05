export default function AnalyzingScreen({ total, current, feed }) {
  const pct = total ? Math.round((current / total) * 100) : 0;

  return (
    <div className="analyzing-card">
      <div className="analyzing-status">
        {total
          ? `Checking sentence ${current} of ${total}…`
          : 'Reading your document…'}
      </div>

      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>

      <div className="live-feed">
        {feed.map((item) => (
          <div key={item.index} className="feed-row">
            <span className={`feed-tag ${item.label === 'COMPLIANT' ? 'compliant' : 'noncompliant'}`}>
              {item.label === 'COMPLIANT' ? 'OK' : 'FLAG'}
            </span>
            <span className="feed-text">
              {item.sentence.length > 90 ? item.sentence.slice(0, 90) + '…' : item.sentence}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
