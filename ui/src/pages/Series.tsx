import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { Link, useParams } from "wouter";
import { api } from "../api/client";
import { useEpisode, useInvalidateSeries, useSeries } from "../api/hooks";
import type { EpisodeSummary, Job, SeriesDetail } from "../api/types";
import { Sketch } from "../components/Sketch";
import { AssetImage, Button, EmptyState, ErrorNote, SketchProgress, Sticker, Tape } from "../components/ui";
import { useI18n } from "../i18n";

export function SeriesPage() {
  const params = useParams<{ name: string }>();
  const name = decodeURIComponent(params.name);
  const { t } = useI18n();
  const { data, error, isLoading } = useSeries(name);
  const invalidate = useInvalidateSeries();
  const addEpisode = useMutation({ mutationFn: () => api.createEpisode(name), onSuccess: () => invalidate(name) });

  if (isLoading) return <p className="page muted">{t("common.loading")}</p>;
  if (error || !data) return <div className="page"><ErrorNote error={error} /><Link href="/">{t("nav.backToShelf")}</Link></div>;

  return (
    <div className="page series">
      <aside className="series__info">
        <SeriesInfo data={data} />
      </aside>
      <section className="series__episodes" aria-labelledby="episodes-heading">
        <div className="section-head">
          <h2 id="episodes-heading" className="section-title">{t("series.episodes")}</h2>
          <Button variant="primary" size="sm" onClick={() => addEpisode.mutate()} disabled={addEpisode.isPending}>
            {t("series.addEpisode")}
          </Button>
        </div>
        <ErrorNote error={addEpisode.error} />
        {data.episodes.length === 0 ? (
          <EmptyState asset="empty-series" title={t("series.emptyTitle")} text={t("series.emptyText")}
                      action={<Button variant="primary" onClick={() => addEpisode.mutate()}>{t("series.addFirst")}</Button>} />
        ) : (
          <ol className="episode-list">
            {data.episodes.map((ep) => (
              <li key={ep.id}><EpisodeRow series={data.name} ep={ep} /></li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function SeriesInfo({ data }: { data: SeriesDetail }) {
  const { t } = useI18n();
  const openFolder = useMutation({ mutationFn: () => api.openFolder(data.name) });
  const pages = data.episodes.reduce((n, e) => n + e.pages, 0);
  const done = data.episodes.reduce((n, e) => n + e.counts.done, 0);
  return (
    <Sketch className="card series-card" radius={22}>
      <Tape color="butter" />
      <div className="series-card__cover">
        {data.cover ? <img src={data.cover} alt="" /> : <AssetImage id="empty-series" />}
      </div>
      <p className="eyebrow">{t(`series.format_${data.settings.format}`)}</p>
      <h1 className="series-card__title">{data.name}</h1>
      <p className="lang-pair">
        <span className="chip chip--static">{t(`lang.${data.settings.source_lang}`)}</span>
        <span aria-hidden="true">→</span>
        <span className="chip chip--static">{t(`lang.${data.settings.target_lang}`)}</span>
      </p>
      <dl className="stats">
        <div><dt>{t("series.statEpisodes")}</dt><dd>{data.episodes.length}</dd></div>
        <div><dt>{t("series.statPages")}</dt><dd>{done} / {pages}</dd></div>
        <div><dt>{t("series.statTerms")}</dt><dd>{data.glossary.confirmed}</dd></div>
      </dl>
      <div className="stack">
        <Link href={`/series/${encodeURIComponent(data.name)}/glossary`} className="linkbtn">
          {t("series.glossary")}
          {data.glossary.pending > 0 && <Sticker color="rose">{t("shelf.pending", { n: data.glossary.pending })}</Sticker>}
        </Link>
        <Button variant="quiet" size="sm" onClick={() => openFolder.mutate()}>{t("series.openFolder")}</Button>
      </div>
    </Sketch>
  );
}

function EpisodeRow({ series, ep }: { series: string; ep: EpisodeSummary }) {
  const { t } = useI18n();
  const { data } = useEpisode(series, ep.id);
  const invalidate = useInvalidateSeries();
  const fileInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [finished, setFinished] = useState<Job | null>(null);
  const lastJob = useRef<Job | null>(null);

  const summary = data ?? ep;
  const job = data?.job ?? null;

  // 工作結束後取回最終結果（完成、警告、錯誤），並更新整個作品的資料
  useEffect(() => {
    if (job) {
      lastJob.current = job;
      setFinished(null);
    } else if (lastJob.current) {
      const id = lastJob.current.id;
      lastJob.current = null;
      api.job(id).then(setFinished).catch(() => {});
      invalidate(series);
    }
  }, [job, series, invalidate]);

  const upload = useMutation({
    mutationFn: (files: File[]) => api.uploadPages(series, ep.id, files),
    onSuccess: () => invalidate(series),
  });
  const run = useMutation({
    mutationFn: ({ steps, force }: { steps: string[]; force?: boolean }) => api.run(series, ep.id, steps, force),
    onSuccess: () => invalidate(series),
  });

  const onFiles = (list: FileList | null) => {
    const files = Array.from(list ?? []).filter((f) => f.type.startsWith("image/"));
    if (files.length) upload.mutate(files);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    onFiles(e.dataTransfer.files);
  };

  const progress = summary.pages ? summary.counts.done / summary.pages : 0;
  const busy = !!job || run.isPending;
  const canRead = summary.counts.done > 0;

  return (
    <Sketch
      className={`episode ${dragging ? "is-dragging" : ""}`}
      radius={18}
      onDragOver={(e: DragEvent) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <div className="episode__head">
        <h3 className="episode__title">{t("series.episodeLabel", { n: summary.label })}</h3>
        <span className="muted">{t("series.pageCount", { n: summary.pages })}</span>
        <span className={`status status--${summary.status}`}>{t(`series.status_${summary.status}`)}</span>
      </div>

      <SketchProgress value={progress} label={t("series.progressLabel", { done: summary.counts.done, total: summary.pages })} />

      {job && (
        <div className="job" aria-live="polite">
          <AssetImage id="mascot-loading" className="job__mascot" />
          <div>
            <p className="job__step">{t(`job.step_${job.step ?? "queued"}`)}</p>
            <p className="muted job__log">{job.log.at(-1) ?? t("job.waiting")}</p>
          </div>
        </div>
      )}
      {!job && finished && <JobResult job={finished} series={series} onDismiss={() => setFinished(null)} />}
      <ErrorNote error={upload.error ?? run.error} />

      <div className="episode__actions">
        <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" multiple hidden
               onChange={(e) => { onFiles(e.target.files); e.target.value = ""; }} />
        <Button size="sm" onClick={() => fileInput.current?.click()} disabled={upload.isPending}>
          {upload.isPending ? t("series.uploading") : t("series.upload")}
        </Button>
        {summary.pages > 0 && summary.status !== "done" && (
          <Button variant="primary" size="sm" disabled={busy} onClick={() => run.mutate({ steps: ["ocr", "translate", "render"] })}>
            {t("series.translate")}
          </Button>
        )}
        {summary.status === "done" && (
          <>
            <Button size="sm" disabled={busy} onClick={() => run.mutate({ steps: ["render"] })}>{t("series.rerender")}</Button>
            <Button size="sm" variant="quiet" disabled={busy}
                    onClick={() => run.mutate({ steps: ["translate", "render"], force: true })}>{t("series.retranslate")}</Button>
          </>
        )}
        {canRead && (
          <Link href={`/read/${encodeURIComponent(series)}/${ep.id}`} className="linkbtn linkbtn--primary">
            {t("series.read")}
          </Link>
        )}
      </div>
      {summary.pages === 0 && <p className="muted hint">{t("series.dropHint")}</p>}
    </Sketch>
  );
}

function JobResult({ job, series, onDismiss }: { job: Job; series: string; onDismiss: () => void }) {
  const { t } = useI18n();
  const ok = job.status === "done";
  return (
    <div className={`notice ${ok ? "notice--ok" : "notice--error"}`} role="status">
      <p>
        {ok ? t("job.done") : t("job.failed", { error: job.error ?? "" })}
        {ok && job.new_terms > 0 && (
          <> {t("job.newTerms", { n: job.new_terms })}{" "}
            <Link href={`/series/${encodeURIComponent(series)}/glossary`}>{t("job.reviewTerms")}</Link>
          </>
        )}
      </p>
      {job.warnings.length > 0 && (
        <details>
          <summary>{t("job.warnings", { n: job.warnings.length })}</summary>
          <ul>{job.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </details>
      )}
      <button type="button" className="notice__close" onClick={onDismiss} aria-label={t("common.close")}>×</button>
    </div>
  );
}
