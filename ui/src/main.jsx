import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

async function get(path, params, signal) {
  const response = await fetch(`${path}?${new URLSearchParams(params)}`, { signal });
  if (!response.ok) throw new Error(`Catalog request failed (${response.status}). Check that the API and database are running.`);
  return response.json();
}

function App() {
  const [query, setQuery] = useState('revenue');
  const [domain, setDomain] = useState('');
  const [kind, setKind] = useState('table');
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState('');
  const [graphError, setGraphError] = useState('');
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState('');
  const request = useRef(null);
  async function runSearch(event, override) {
    event?.preventDefault();
    const text = (override ?? query).trim();
    if (!text) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true); setError(''); setSelected(null); setResults([]); setGraph(null);
    try {
      const data = await get('/api/search', { q: text, ...(domain && { domain }), ...(kind && { kind }) }, controller.signal);
      setResults(data.results); setSelected(data.results[0] ?? null); setSearched(text);
    } catch (e) { if (e.name !== 'AbortError') setError(e.message); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  }
  useEffect(() => { runSearch(); return () => request.current?.abort(); }, []);
  useEffect(() => {
    setGraph(null); setGraphError('');
    if (!selected) return;
    const controller = new AbortController();
    get('/api/graph/neighbors', { asset_id: selected.kind === 'column' ? selected.parent_id : selected.id }, controller.signal)
      .then(setGraph).catch(e => { if (e.name !== 'AbortError') setGraphError(e.message); });
    return () => controller.abort();
  }, [selected]);
  return <div className="shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="Atlas home"><span className="brand-icon"><svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M7 24 16 7l9 17M11 19h10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/><circle cx="16" cy="7" r="2" fill="currentColor"/></svg></span> atlas<span className="brand-dot">.</span></a>
      <div className="workspace"><span className="workspace-icon">K</span><div>Knowledge workspace<small>Local development</small></div><span>⌄</span></div>
      <p className="nav-label">WORKSPACE</p><div className="nav-item active"><span>⌕</span> Catalog explorer <b>01</b></div>
      <div className="sidebar-note">Built for context.<br/>Grounded in metadata.</div>
      <div className="offline"><span/> Mock warehouse<small>No external connections</small></div>
    </aside>
    <main>
      <header><span>Workspace <span className="slash">/</span> <strong>Catalog explorer</strong></span><span className="environment">OFFLINE DEMO</span></header>
      <section className="intro"><div className="intro-copy"><div className="eyebrow">YOUR DATA, CONNECTED</div><h1>Find the right <span>context.</span></h1><p>Explore trusted schema metadata, understand relationships,<br className="desktop"/> and give your agents a clearer picture.</p></div><div className="context-orbit" aria-hidden="true"><div className="orbit-ring ring-one"/><div className="orbit-ring ring-two"/><div className="orbit-core">◇</div><i className="orbit-node node-one"/><i className="orbit-node node-two"/><i className="orbit-node node-three"/></div></section>
      <form onSubmit={runSearch} className="search-form"><div className="search-input"><span aria-hidden="true">⌕</span><input aria-label="Search catalog" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search tables, columns, or business concepts…" maxLength={300}/><button disabled={loading || !query.trim()}>{loading ? 'Searching…' : 'Search'} <span>↗</span></button></div>
        <div className="filters"><label>Domain <select value={domain} onChange={e => setDomain(e.target.value)}><option value="">All domains</option>{['commerce', 'finance', 'product'].map(d => <option key={d}>{d}</option>)}</select></label><label>Asset type <select value={kind} onChange={e => setKind(e.target.value)}><option value="">All assets</option><option value="table">Tables</option><option value="column">Columns</option><option value="dataset">Datasets</option></select></label><span className="filter-hint">Full-text search + usage signals</span></div>
      </form>
      <div className="suggestions"><span>Try a concept</span>{['revenue', 'customer profiles', 'feature adoption'].map(q => <button key={q} onClick={() => { setQuery(q); runSearch(null, q); }}>{q} ↗</button>)}</div>
      {error && <div role="alert" className="error">{error}</div>}
      <div className="results-heading"><h2>Catalog results <span>{results.length}</span></h2><span>{searched && `Matches for “${searched}”`}</span></div>
      <div className="content-grid"><section className="results" aria-label="Search results" aria-busy={loading}>
        {!loading && !error && results.length === 0 && <div className="empty">No matching metadata. Try fewer words or another domain.</div>}
        {results.map((asset, index) => <button key={asset.id} className={`result-card ${selected?.id === asset.id ? 'selected' : ''}`} onClick={() => setSelected(asset)} aria-pressed={selected?.id === asset.id}>
          <div className="result-top"><span className={`domain ${asset.domain}`}>{asset.domain}</span><span className="asset-kind">▦ {asset.kind}</span><span className="rank">#{index + 1}</span></div>
          <h3>{asset.name}<span>↗</span></h3><div className="asset-id">{asset.id}</div><p>{asset.description}</p>
          <div className="result-bottom"><span className={asset.unused ? 'muted' : ''}>● {asset.unused == null ? 'Usage not enriched' : asset.unused ? 'Unused in last 7 days' : `${asset.query_count_7d} queries / 7d`}</span><span>Relevance <strong>{asset.score.toFixed(3)}</strong></span></div>
        </button>)}
      </section><aside className="detail-panel">
        <div className="panel-heading"><span>CONTEXT & RELATIONSHIPS</span><span>◇</span></div>
        {selected ? <><h2>{selected.name}</h2><p className="detail-description">{selected.description}</p><div className="owner"><span>Owner</span><strong>{selected.owners.join(', ')}</strong></div>
          <h4>Why this result</h4>{Object.entries(selected.explanation.components).map(([name, value]) => <div className="signal" key={name}><span>{name.replaceAll('_', ' ')}</span><div><i style={{ width: `${Math.max(0, Math.min(100, value / 0.7 * 100))}%` }}/></div><b>{value.toFixed(3)}</b></div>)}
          <p className="microcopy">Weighted contributions sum to the relevance score. Usage is measured at table level.</p>
          <div className="lineage-title"><h4>Connected assets</h4><span>{graph?.edges.length ?? '…'}</span></div>
          {graphError ? <p role="alert" className="error">{graphError}</p> : !graph ? <p className="microcopy">Loading relationships…</p> : graph.edges.length ? <ul className="edges">{graph.edges.map(e => <li key={`${e.source_id}-${e.target_id}-${e.kind}`}><span className={`edge-type ${e.kind}`}>{e.kind.replace('_', ' ')}</span><div>{e.source_id}<span>↓</span>{e.target_id}</div>{e.kind === 'join' && <small>{e.source_column} = {e.target_column}</small>}</li>)}</ul> : <p className="microcopy">No recorded relationships for this asset.</p>}
          <a className="context-link" href={`/api/context?${new URLSearchParams({q: searched, limit: '5'})}`} target="_blank" rel="noreferrer">Open agent context JSON <span>↗</span></a>
        </> : <p className="empty">Select a result to explore its context.</p>}
      </aside></div><footer>ATLAS / KNOWLEDGE CATALOG<span>Schema → signals → context</span></footer>
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
