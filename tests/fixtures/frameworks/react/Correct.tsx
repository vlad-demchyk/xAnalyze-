export function Panel({ onClose, photo, query, update }) {
  return <div className="panel">
    <button onClick={onClose} aria-label="Close">×</button>
    <label htmlFor="q">Search</label>
    <input id="q" onChange={update} value={query} />
    <img src={photo.url} alt={photo.caption} />
    <a href="/help">Help</a>
  </div>;
}
