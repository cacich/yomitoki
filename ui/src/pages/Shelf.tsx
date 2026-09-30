import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useLocation } from "wouter";
import { api } from "../api/client";
import { keys, useShelf, useStatus } from "../api/hooks";
import type { ShelfItem } from "../api/types";
import { Sketch } from "../components/Sketch";
import { AssetImage, Button, Dialog, EmptyState, ErrorNote, Sticker, Tape } from "../components/ui";
import { useI18n } from "../i18n";

const SPINES = ["var(--color-terracotta)", "var(--color-sage)", "var(--color-butter)", "var(--color-rose)"];
const TAPES = ["rose", "butter", "sage"] as const;

export function Shelf() {
  const { t } = useI18n();
  const { data, isLoading, error } = useShelf();
  const [creating, setCreating] = useState(false);
  const today = new Date();

  return (
    <div className="page">
      <section className="masthead">
        <p className="masthead__issue">{t("shelf.issue", { year: today.getFullYear(), month: today.getMonth() + 1 })}</p>
        <h1 className="masthead__title">{t("shelf.title")}</h1>
        <p className="masthead__lead">{t("shelf.lead")}</p>
        <Button variant="primary" onClick={() => setCreating(true)}>{t("shelf.new")}</Button>
      </section>

      <ErrorNote error={error} />
      {isLoading && <p className="muted">{t("common.loading")}</p>}
      {data && data.length === 0 && (
        <EmptyState asset="empty-shelf" title={t("shelf.emptyTitle")} text={t("shelf.emptyText")}
                    action={<Button variant="primary" onClick={() => setCreating(true)}>{t("shelf.new")}</Button>} />
      )}
      {data && data.length > 0 && (
        <ul className="shelf-grid">
          {data.map((item, i) => (
            <li key={item.name}><BookCard item={item} index={i} /></li>
          ))}
        </ul>
      )}
      <CreateSeriesDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function BookCard({ item, index }: { item: ShelfItem; index: number }) {
  const { t } = useI18n();
  return (
    <Link href={`/series/${encodeURIComponent(item.name)}`} className="book">
      <Sketch className="book__card" radius={18}>
        <Tape color={TAPES[index % TAPES.length]} side={index % 2 ? "right" : "left"} />
        <div className="book__cover">
          {item.cover ? <img src={item.cover} alt="" loading="lazy" /> : <AssetImage id="empty-series" className="book__placeholder" />}
          <span className="book__spine" style={{ background: SPINES[index % SPINES.length] }} aria-hidden="true">
            <span>{item.name}</span>
          </span>
        </div>
        <div className="book__meta">
          <h3 className="book__title">{item.name}</h3>
          <p className="muted">
            {t("shelf.meta", { episodes: item.episodes, done: item.done_pages, pages: item.pages })}
          </p>
        </div>
        {item.pending_terms > 0 && (
          <span className="book__sticker"><Sticker color="rose">{t("shelf.pending", { n: item.pending_terms })}</Sticker></span>
        )}
      </Sketch>
    </Link>
  );
}

function CreateSeriesDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const { data: status } = useStatus();
  const qc = useQueryClient();
  const [, navigate] = useLocation();
  const [name, setName] = useState("");
  const [format, setFormat] = useState("page");
  const [source, setSource] = useState("ja");
  const [target, setTarget] = useState("zh-TW");

  const create = useMutation({
    mutationFn: () => api.createSeries({ name: name.trim(), format, source_lang: source, target_lang: target }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: keys.shelf });
      onClose();
      setName("");
      navigate(`/series/${encodeURIComponent(res.name)}`);
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (name.trim()) create.mutate();
  };

  return (
    <Dialog open={open} onClose={onClose} title={t("shelf.newTitle")}>
      <form className="form" onSubmit={submit}>
        <label className="field">
          <span className="field__label">{t("series.name")}</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoFocus required maxLength={120}
                 placeholder={t("series.namePlaceholder")} />
        </label>
        <label className="field">
          <span className="field__label">{t("series.format")}</span>
          <select className="input" value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="page">{t("series.formatPage")}</option>
            <option value="scroll" disabled>{t("series.formatScroll")}（v0.2）</option>
          </select>
        </label>
        <div className="field-row">
          <label className="field">
            <span className="field__label">{t("series.source")}</span>
            <select className="input" value={source} onChange={(e) => setSource(e.target.value)}>
              {status?.languages.sources.map((l) => (
                <option key={l.code} value={l.code} disabled={l.status !== "supported"}>
                  {l.name}{l.status !== "supported" ? `（${t("common.planned")}）` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">{t("series.target")}</span>
            <select className="input" value={target} onChange={(e) => setTarget(e.target.value)}>
              {status?.languages.targets.map((l) => (
                <option key={l.code} value={l.code} disabled={l.status !== "supported"}>
                  {l.name}{l.status !== "supported" ? `（${t("common.planned")}）` : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
        <ErrorNote error={create.error} />
        <div className="form__actions">
          <Button variant="quiet" onClick={onClose}>{t("common.cancel")}</Button>
          <Button variant="primary" type="submit" disabled={!name.trim() || create.isPending}>
            {create.isPending ? t("common.saving") : t("shelf.create")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
