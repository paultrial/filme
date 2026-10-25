type Entity = { claims?: Record<string, Array<{ mainsnak?: { datavalue?: { value?: unknown } } }>> };

const value = (entity: Entity | undefined, property: string) => entity?.claims?.[property]?.[0]?.mainsnak?.datavalue?.value;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const title = searchParams.get("title")?.trim();
  const year = searchParams.get("year")?.trim();
  if (!title) return Response.json({ error: "A title is required" }, { status: 400 });

  try {
    const query = new URLSearchParams({ action: "query", format: "json", origin: "*", generator: "search", gsrsearch: `${title}${year ? ` ${year}` : ""}`, gsrnamespace: "0", gsrlimit: "1", prop: "extracts|pageimages|pageprops", exintro: "1", explaintext: "1", piprop: "thumbnail", pithumbsize: "500" });
    const wiki = await fetch(`https://en.wikipedia.org/w/api.php?${query}`, { next: { revalidate: 604800 } }).then(r => r.json());
    const page = Object.values(wiki.query?.pages ?? {})[0] as { extract?: string; thumbnail?: { source?: string }; pageprops?: { wikibase_item?: string } } | undefined;
    const qid = page?.pageprops?.wikibase_item;
    if (!page) return Response.json({});

    let runtime: number | undefined, cast: string[] = [];
    const genres: string[] = [];
    if (qid) {
      const entity = await fetch(`https://www.wikidata.org/wiki/Special:EntityData/${qid}.json`, { next: { revalidate: 604800 } }).then(r => r.json()) as { entities?: Record<string, Entity> };
      const item = entity.entities?.[qid];
      const duration = value(item, "P2047") as { amount?: string } | undefined;
      runtime = duration?.amount ? Math.round(Number(duration.amount.replace("+", ""))) : undefined;
      const castClaims = item?.claims?.P161?.slice(0, 4) ?? [];
      const ids = castClaims.map(claim => ((claim.mainsnak?.datavalue?.value as { id?: string } | undefined)?.id)).filter(Boolean) as string[];
      if (ids.length) {
        const people = await fetch(`https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=labels&languages=en&ids=${ids.join("|")}`, { next: { revalidate: 604800 } }).then(r => r.json()) as { entities?: Record<string, { labels?: { en?: { value?: string } } }> };
        cast = ids.map(id => people.entities?.[id]?.labels?.en?.value).filter(Boolean) as string[];
      }
    }
    return Response.json({ description: page.extract, poster: page.thumbnail?.source, runtime, cast, genres });
  } catch {
    return Response.json({});
  }
}
