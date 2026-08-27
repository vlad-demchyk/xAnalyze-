export function Panel({ onClose, photo, query, update }) {
  return <div className="panel">
    <button onClick={onClose}></button>
    <input onChange={update} value={query} placeholder="Search" />
    <img src={photo.url} />
    <a href="/help"><svg aria-hidden="true" /></a>
  </div>;
}
