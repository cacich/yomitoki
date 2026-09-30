import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "wouter";
import { api } from "../api/client";
import { keys, useGlossary, useInvalidateSeries, useNotes } from "../api/hooks";
import type { Glossary, Term } from "../api/types";
import { Sketch } from "../components/Sketch";
import { Button, EmptyState, ErrorNote, Sticker, Tape } from "../components/ui";
import { useI18n } from "../i18n";

const CATEGORIES: Term["category"][] = ["character", "place", "technique", "item", "other"];

export function GlossaryPage() {
  const params = useParams<{ name: string }>();
  const name = decodeURIComponent(params.name);
  const { t } = useI18n();
  const { data, error } = useGlossary(name);
  const qc = useQueryClient();
  const invalidate = useInvalidateSeries();
  const [changed, setChanged] = useState(false);

  const onSaved = (g: Glossary) => {
    qc.setQueryData(keys.glossary(name), g);
    invalidate(name);
    setChanged(true);
  };

  const pending = data?.terms.filter((x) => x.status === "pending") ?? [];
  const confirmed = data?.terms.filter((x) => x.status === "confirmed") ?? [];

  return (
    <div className="page glossary">
      <Link href={`/series/${encodeURIComponent(name)}`} className="backlink">← {name}</Link>
      <header className="page-head">
        <h1 className="page-title">{t("glossary.title")}</h1>
        <p className="muted">{t("glossary.lead")}</p>
      </header>
      <ErrorNote error={error} />
      {changed && (
        <p className="notice notice--ok">
          {t("glossary.changedHint")}{" "}
          <Link href={`/series/${encodeURIComponent(name)}`}>{t("glossary.goRetranslate")}</Link>
        </p>
      )}

      {pending.length > 0 && (
        <section className="notebook notebook--pending" aria-labelledby="pending-heading">
          <Tape color="rose" />
          <h2 id="pending-heading" className="section-title">
            {t("glossary.pending")} <Sticker color="rose">{pending.length}</Sticker>
          </h2>
          <p className="muted">{t("glossary.pendingLead")}</p>
          <ul className="pending-list">
            {pending.map((term) => <PendingRow key={term.source} series={name} term={term} onSaved={onSaved} />)}
          </ul>
        </section>
      )}

      <section className="notebook" aria-labelledby="confirmed-heading">
        <h2 id="confirmed-heading" className="section-title">{t("glossary.confirmed")}</h2>
        {data && confirmed.length === 0 && pending.length === 0 ? (
          <EmptyState asset="mascot-guide" title={t("glossary.emptyTitle")} text={t("glossary.emptyText")} />
        ) : (
          <table className="terms">
            <thead>
              <tr>
                <th scope="col">{t("glossary.source")}</th>
                <th scope="col">{t("glossary.target")}</th>
                <th scope="col">{t("glossary.category")}</th>
                <th scope="col">{t("glossary.note")}</th>
                <th scope="col"><span className="visually-hidden">{t("glossary.actions")}</span></th>
              </tr>
            </thead>
            <tbody>
              {confirmed.map((term) => <ConfirmedRow key={term.source} series={name} term={term} onSaved={onSaved} />)}
            </tbody>
          </table>
        )}
        <AddTerm series={name} onSaved={onSaved} />
      </section>

      <Notes series={name} />
    </div>
  );
}

function CategorySelect({ value, onChange }: { value: Term["category"]; onChange: (v: Term["category"]) => void }) {
  const { t } = useI18n();
  return (
    <select className="input input--sm" value={value} onChange={(e) => onChange(e.target.value as Term["category"])}
            aria-label={t("glossary.category")}>
      {CATEGORIES.map((c) => <option key={c} value={c}>{t(`glossary.cat_${c}`)}</option>)}
    </select>
  );
}

function PendingRow({ series, term, onSaved }: { series: string; term: Term; onSaved: (g: Glossary) => void }) {
  const { t } = useI18n();
  const [target, setTarget] = useState(term.target);
  const [category, setCategory] = useState(term.category);
  const confirm = useMutation({
    mutationFn: () => api.setTerm(series, { source: term.source, target: target.trim(), category, note: term.note }),
    onSuccess: onSaved,
  });
  const remove = useMutation({ mutationFn: () => api.removeTerm(series, term.source), onSuccess: onSaved });
  const [ep, stem] = term.first_seen.split("/");

  return (
    <li className="pending">
      {term.thumb ? (
        <Link href={`/read/${encodeURIComponent(series)}/${ep}/${stem}`} className="pending__thumb" title={t("glossary.seenAt", { where: term.first_seen })}>
          <img src={term.thumb} alt={t("glossary.seenAt", { where: term.first_seen })} loading="lazy" />
        </Link>
      ) : <span className="pending__thumb pending__thumb--none" />}
      <div className="pending__body">
        <p className="pending__source">{term.source}</p>
        <p className="muted small">{term.first_seen && t("glossary.seenAt", { where: term.first_seen })}</p>
        <div className="pending__edit">
          <input className="input input--sm" value={target} onChange={(e) => setTarget(e.target.value)}
                 aria-label={t("glossary.targetFor", { source: term.source })} />
          <CategorySelect value={category} onChange={setCategory} />
          <Button size="sm" variant="primary" disabled={!target.trim() || confirm.isPending} onClick={() => confirm.mutate()}>
            {t("glossary.confirm")}
          </Button>
          <Button size="sm" variant="quiet" onClick={() => remove.mutate()}>{t("glossary.remove")}</Button>
        </div>
        <ErrorNote error={confirm.error ?? remove.error} />
      </div>
    </li>
  );
}

function ConfirmedRow({ series, term, onSaved }: { series: string; term: Term; onSaved: (g: Glossary) => void }) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [target, setTarget] = useState(term.target);
  const [category, setCategory] = useState(term.category);
  const [note, setNote] = useState(term.note);
  const save = useMutation({
    mutationFn: () => api.setTerm(series, { source: term.source, target: target.trim(), category, note }),
    onSuccess: (g) => { setEditing(false); onSaved(g); },
  });
  const remove = useMutation({ mutationFn: () => api.removeTerm(series, term.source), onSuccess: onSaved });

  if (!editing) {
    return (
      <tr>
        <td className="terms__source">{term.source}</td>
        <td className="terms__target">{term.target}</td>
        <td>{t(`glossary.cat_${term.category}`)}</td>
        <td className="muted">{term.note}</td>
        <td className="terms__actions">
          <Button size="sm" variant="quiet" onClick={() => setEditing(true)}>{t("common.edit")}</Button>
        </td>
      </tr>
    );
  }
  return (
    <tr className="is-editing">
      <td className="terms__source">{term.source}</td>
      <td><input className="input input--sm" value={target} onChange={(e) => setTarget(e.target.value)}
                 aria-label={t("glossary.targetFor", { source: term.source })} autoFocus /></td>
      <td><CategorySelect value={category} onChange={setCategory} /></td>
      <td><input className="input input--sm" value={note} onChange={(e) => setNote(e.target.value)} aria-label={t("glossary.note")} /></td>
      <td className="terms__actions">
        <Button size="sm" variant="primary" disabled={!target.trim() || save.isPending} onClick={() => save.mutate()}>{t("common.save")}</Button>
        <Button size="sm" variant="quiet" onClick={() => setEditing(false)}>{t("common.cancel")}</Button>
        <Button size="sm" variant="quiet" onClick={() => remove.mutate()}>{t("glossary.remove")}</Button>
        <ErrorNote error={save.error ?? remove.error} />
      </td>
    </tr>
  );
}

function AddTerm({ series, onSaved }: { series: string; onSaved: (g: Glossary) => void }) {
  const { t } = useI18n();
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [category, setCategory] = useState<Term["category"]>("character");
  const add = useMutation({
    mutationFn: () => api.setTerm(series, { source: source.trim(), target: target.trim(), category }),
    onSuccess: (g) => { setSource(""); setTarget(""); onSaved(g); },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (source.trim() && target.trim()) add.mutate();
  };
  return (
    <form className="add-term" onSubmit={submit}>
      <input className="input input--sm" placeholder={t("glossary.source")} value={source} onChange={(e) => setSource(e.target.value)}
             aria-label={t("glossary.source")} />
      <span aria-hidden="true">→</span>
      <input className="input input--sm" placeholder={t("glossary.target")} value={target} onChange={(e) => setTarget(e.target.value)}
             aria-label={t("glossary.target")} />
      <CategorySelect value={category} onChange={setCategory} />
      <Button size="sm" type="submit" disabled={!source.trim() || !target.trim() || add.isPending}>{t("glossary.add")}</Button>
      <ErrorNote error={add.error} />
    </form>
  );
}

function Notes({ series }: { series: string }) {
  const { t } = useI18n();
  const { data } = useNotes(series);
  const qc = useQueryClient();
  const [rules, setRules] = useState("");
  const [summary, setSummary] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setRules(data.rules);
      setSummary(data.summary);
    }
  }, [data]);

  const save = useMutation({
    mutationFn: () => api.saveNotes(series, { rules, summary }),
    onSuccess: (n) => { qc.setQueryData(keys.notes(series), n); setSaved(true); },
  });
  const dirty = !!data && (rules !== data.rules || summary !== data.summary);

  return (
    <section className="notes" aria-labelledby="notes-heading">
      <h2 id="notes-heading" className="section-title">{t("glossary.notes")}</h2>
      <div className="notes__grid">
        <Sketch className="card" radius={18}>
          <label className="field">
            <span className="field__label">{t("glossary.rules")}</span>
            <span className="muted small">{t("glossary.rulesHint")}</span>
            <textarea className="input textarea" rows={10} value={rules} onChange={(e) => { setRules(e.target.value); setSaved(false); }} />
          </label>
        </Sketch>
        <Sketch className="card" radius={18}>
          <label className="field">
            <span className="field__label">{t("glossary.summary")}</span>
            <span className="muted small">{t("glossary.summaryHint")}</span>
            <textarea className="input textarea" rows={10} value={summary} onChange={(e) => { setSummary(e.target.value); setSaved(false); }} />
          </label>
        </Sketch>
      </div>
      <div className="form__actions">
        {saved && !dirty && <span className="muted">{t("common.saved")}</span>}
        <Button variant="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>{t("common.save")}</Button>
      </div>
      <ErrorNote error={save.error} />
    </section>
  );
}
