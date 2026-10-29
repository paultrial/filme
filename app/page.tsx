import { readFile } from "node:fs/promises";
import path from "node:path";
import MoviePicker from "./movie-picker";

export type LibraryMovie = {
  id: number;
  filename: string;
  title: string;
  year: number | null;
};

function cleanFilename(filename: string, id: number): LibraryMovie {
  const bare = filename.replace(/\.[a-z0-9]+$/i, "");
  const match = bare.match(/(?:^|\s|\()(19\d{2}|20\d{2})(?:\s|\)|$)/);
  const year = match ? Number(match[1]) : null;
  const title = (match ? bare.slice(0, match.index) : bare).replace(/[._-]+/g, " ").trim();
  return { id, filename, title: title || "Untitled", year };
}

async function getMovies() {
  const source = await readFile(path.join(process.cwd(), "public", "filme.txt"), "utf8");
  return source.split(/\r?\n/).filter(Boolean).map(cleanFilename);
}

export default function Home() {
  return <MoviePicker initialMovies={[]} />;
}
