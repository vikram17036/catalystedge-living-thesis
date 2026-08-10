import { ExternalLink, Newspaper } from 'lucide-react';
import type { NewsArticle } from '../types/api';

interface NewsSourcesProps {
  articles?: NewsArticle[];
}

const formatDate = (value: string) => {
  if (!value) return 'Date unavailable';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Date unavailable';

  return date.toLocaleDateString();
};

export default function NewsSources({ articles = [] }: NewsSourcesProps) {
  const visibleArticles = articles
    .filter((article) => article.title)
    .slice(0, 5);

  if (visibleArticles.length === 0) {
    return null;
  }

  return (
    <section className="overflow-hidden rounded-sm border border-border-base bg-surface-1">
      <div className="flex items-center gap-2 border-b border-border-base/50 bg-surface-2 px-4 py-2">
        <Newspaper className="h-3 w-3 text-txt-muted" />
        <h3 className="font-mono text-micro font-bold uppercase tracking-widest text-txt-primary">
          SOURCES_AND_CITATIONS
        </h3>
      </div>

      <div className="divide-y divide-border-base/50 bg-canvas">
        {visibleArticles.map((article, index) => (
          <div key={`${article.url}-${index}`} className="p-4">
            <div className="flex gap-3">
              <span className="shrink-0 font-mono text-micro font-bold text-accent">
                [{index + 1}]
              </span>

              <div className="min-w-0 flex-1">
                {article.url ? (
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noreferrer"
                    className="group inline-flex items-start gap-2 font-mono text-sm font-bold leading-relaxed text-txt-primary hover:text-accent"
                  >
                    <span>{article.title}</span>
                    <ExternalLink className="mt-1 h-3 w-3 shrink-0 opacity-60 transition-opacity group-hover:opacity-100" />
                  </a>
                ) : (
                  <p className="font-mono text-sm font-bold leading-relaxed text-txt-primary">
                    {article.title}
                  </p>
                )}

                <p className="mt-2 font-mono text-micro uppercase tracking-widest text-txt-muted">
                  {article.source || 'Unknown source'} · {formatDate(article.published_at)}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
