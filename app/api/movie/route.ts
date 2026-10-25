type TmdbMovie = { id: number; title: string; release_date?: string };
type TmdbDetails = {
  poster_path?: string | null;
  overview?: string;
  release_date?: string;
  runtime?: number | null;
  vote_average?: number;
  genres?: Array<{ name: string }>;
  external_ids?: { imdb_id?: string | null };
  credits?: { cast?: Array<{ name: string }> };
};

const tmdb = async <T,>(path: string) => {
  const token = process.env.TMDB_READ_ACCESS_TOKEN;
  if (!token) throw new Error("TMDB_READ_ACCESS_TOKEN is not configured");
  const response = await fetch(`https://api.themoviedb.org/3${path}`, {
    headers: { Authorization: `Bearer ${token}`, accept: "application/json" },
    next: { revalidate: 604800 },
  });
  if (!response.ok) throw new Error(`TMDB request failed (${response.status})`);
  return response.json() as Promise<T>;
};

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const title = searchParams.get("title")?.trim();
  const year = searchParams.get("year")?.trim();
  if (!title) return Response.json({ error: "A title is required" }, { status: 400 });

  try {
    const query = new URLSearchParams({ query: title, ...(year ? { year } : {}) });
    const search = await tmdb<{ results: TmdbMovie[] }>(`/search/movie?${query}`);
    const movie = search.results[0];
    if (!movie) return Response.json({});
    const details = await tmdb<TmdbDetails>(`/movie/${movie.id}?append_to_response=credits,external_ids`);
    return Response.json({
      poster: details.poster_path ? `https://image.tmdb.org/t/p/w500${details.poster_path}` : undefined,
      description: details.overview,
      year: details.release_date?.slice(0, 4),
      runtime: details.runtime,
      genres: details.genres?.map(genre => genre.name) ?? [],
      cast: details.credits?.cast?.slice(0, 4).map(person => person.name) ?? [],
      tmdbRating: details.vote_average ? Number(details.vote_average.toFixed(1)) : undefined,
      imdbId: details.external_ids?.imdb_id ?? undefined,
    });
  } catch (error) {
    console.error("TMDB lookup failed", error);
    return Response.json({ error: "Movie metadata could not be loaded" }, { status: 502 });
  }
}
