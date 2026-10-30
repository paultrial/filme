"use client";

import { useMemo, useState, useEffect } from "react";
import type { LibraryMovie } from "./page";

type MovieMetadata = {
  title?: string;
  genre?: string;
  overview?: string;
  poster_path?: string;
  cast?: string[];
  not_found?: boolean;
  error?: string;
};

type Movie = LibraryMovie & { genre: string; color: string; poster?: string };
const genres = ["All", "Drama", "Thriller", "Comedy", "Documentary", "Action", "Animation", "Horror", "Music"];
const palette = ["#38444c", "#a04535", "#53624d", "#695877", "#ba7c42", "#36566a", "#7c3e50", "#696041"];
const hash = (text: string) => [...text].reduce((n, c) => (n * 31 + c.charCodeAt(0)) >>> 0, 7);
function decorate(movie: LibraryMovie): Movie { const code = hash(movie.title); return { ...movie, genre: genres.slice(1)[code % (genres.length - 1)], color: palette[code % palette.length] }; }

export default function MoviePicker({ initialMovies }: { initialMovies: LibraryMovie[] }) {
  const [movies, setMovies] = useState<LibraryMovie[]>(initialMovies);
  const [query, setQuery] = useState("");
  const [genre, setGenre] = useState("All");
  const [saved, setSaved] = useState<number[]>([]);
  const [playing, setPlaying] = useState<number | null>(null);
  const [playMessage, setPlayMessage] = useState("");
  const [scanning, setScanning] = useState(false);
  const [metadata, setMetadata] = useState<Record<number, MovieMetadata>>(() => {
    if (typeof window !== "undefined") {
      const cached = localStorage.getItem("filme-metadata");
      return cached ? JSON.parse(cached) : {};
    }
    return {};
  });

  useEffect(() => {
    const fetchMovies = async () => {
      try {
        const res = await fetch("/public/filme.txt");
        if (!res.ok) throw new Error("Could not fetch filme.txt");
        const text = await res.text();

        const cleanFilename = (filename: string, id: number): LibraryMovie => {
          const bare = filename.replace(/\.[a-z0-9]+$/i, "");
          const match = bare.match(/(?:^|\s|\()(19\d{2}|20\d{2})(?:\s|\)|$)/);
          const year = match ? Number(match[1]) : null;
          const title = (match ? bare.slice(0, match.index) : bare).replace(/[._-]+/g, " ").trim();
          return { id, filename, title: title || "Untitled", year };
        };

        const list = text.split(/\r?\n/).filter(Boolean).map((f, i) => cleanFilename(f, i));
        setMovies(list);
      } catch (e) {
        console.error("Error loading movies:", e);
      }
    };

    fetchMovies();
  }, []);

  useEffect(() => {
    let isMounted = true;
    const fetchAllMetadata = async () => {
      for (const movie of movies) {
        if (!isMounted) break;

        try {
          const res = await fetch(`/api/metadata?title=${encodeURIComponent(movie.title)}&year=${movie.year || ""}`);
          if (res.ok) {
            const data = await res.json();
            if (data && !data.error && !data.not_found) {
              setMetadata(prev => ({ ...prev, [movie.id]: data }));
            } else {
              setMetadata(prev => ({ ...prev, [movie.id]: { not_found: true } }));
            }
          }
        } catch (e) {
          console.error(e);
        }
      }
    };
    fetchAllMetadata();
    return () => { isMounted = false; };
  }, [movies]);

  const results = useMemo(() => movies.map(decorate).filter((movie) => (!query || movie.title.toLowerCase().includes(query.toLowerCase())) && (genre === "All" || movie.genre === genre)).sort((a, b) => a.title.localeCompare(b.title)), [movies, query, genre]);
  const toggle = (id: number) => setSaved((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const scanMovies = async () => {
    setScanning(true);
    setPlayMessage("Scanning for new movies...");
    try {
      const res = await fetch("/api/scan", { method: "POST" });
      if (!res.ok) throw new Error("Failed to scan movies");
      setPlayMessage("Movies list updated! Refreshing...");
      setTimeout(() => window.location.reload(), 2000);
    } catch (e) {
      setPlayMessage(e instanceof Error ? e.message : "Error scanning movies");
    } finally {
      setScanning(false);
    }
  };
  const playMovie = async (movie: Movie) => { setPlaying(movie.id); setPlayMessage(""); try { const response = await fetch("/api/play", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: movie.filename }) }); const result = (await response.json().catch(() => ({}))) as { error?: string }; if (!response.ok) throw new Error(result.error || "Could not reach Kodi"); setPlayMessage(`Playing ${movie.title} on Kodi.`); } catch (error) { setPlayMessage(error instanceof Error ? error.message : "Could not reach Kodi"); } finally { setPlaying(null); } };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">fi<i>l</i>me.</div>
        <div className="library-count">{movies.length} titles</div>
        <button className="scan-btn" onClick={scanMovies} disabled={scanning}>{scanning ? "Scanning..." : "Refresh Library"}</button>
      </header>
      <section className="hero">
        <div>
          <div className="eyebrow">A better way to press play</div>
          <h1>Tonight deserves a good movie.</h1>
        </div>
        <p className="hero-copy">Pick a film here and it will start on your Kodi TV.</p>
      </section>
      <section className="controls">
        <div className="control search">
          <label htmlFor="search">Search shelf</label>
          <input id="search" placeholder="Try “Blade Runner”" value={query} onChange={(event) => setQuery(event.target.value)} />
        </div>
      </section>
      <nav className="genre-row" aria-label="Filter by genre">
        <span className="filter-label">Genre</span>
        {genres.map((item) => <button key={item} className={`pill ${genre === item ? "active" : ""}`} onClick={() => setGenre(item)}>{item}</button>)}
      </nav>
      <div className="results-heading">
        <h2>{genre === "All" ? "All films" : genre}</h2>
        <span>{results.length} found</span>
      </div>
      <p className={`play-status ${playMessage ? "visible" : ""}`} role="status">{playMessage}</p>
      {results.length ? (
        <section className="grid">
          {results.map((movie) => {
            const meta = metadata[movie.id];
            return (
              <article className="movie" key={movie.id}>
                <button aria-label={`Save ${movie.title}`} className={`pick ${saved.includes(movie.id) ? "saved" : ""}`} onClick={() => toggle(movie.id)}>{saved.includes(movie.id) ? "✓" : "+"}</button>
                <div className="poster" style={{
                  backgroundImage: meta?.poster_path ? `url(${meta.poster_path.startsWith('/public') ? meta.poster_path : `https://image.tmdb.org/t/p/w500${meta.poster_path}`})` : undefined,
                  backgroundColor: movie.color,
                  backgroundPosition: "center",
                  backgroundSize: "cover"
                }}>
                  {!meta?.poster_path && (
                    <>
                      <small>ON YOUR SHELF</small>
                      <span>{movie.title.split(" ").slice(0, 3).join(" ")}</span>
                      <small>{movie.year ?? "—"}</small>
                    </>
                  )}
                </div>
                <div className="movie-copy">
                  <div className="title-line">
                    <h3>{meta?.title || movie.title}</h3>
                    <span className="year">{movie.year ?? "—"}</span>
                  </div>
                  <span className="genre">{meta?.genre || movie.genre}</span>
                  <div className="cast-list">
                    {meta?.cast?.map((actor: string) => <span key={actor}>{actor}</span>)}
                  </div>
                  {meta?.overview && <p className="description">{meta.overview}</p>}
                  <button className="play" disabled={playing === movie.id} onClick={() => playMovie(movie)}>{playing === movie.id ? "Starting…" : "Play on TV"}</button>
                  <a href={`https://www.imdb.com/find/?q=${encodeURIComponent(movie.title)}&ref_=hm_nv_srb_sm`} target="_blank" rel="noopener noreferrer" className="imdb-link">
                    <img src="/IMDb-Logo.png" alt="IMDb" />
                  </a>
                </div>
              </article>
            );
          })}
        </section>
      ) : (
        <div className="empty">Nothing matches that combination. Try widening the filters.</div>
      )}
    </main>
  );
}
