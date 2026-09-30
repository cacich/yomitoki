import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, type ReactNode } from "react";
import { api } from "../api/client";
import { keys, useAssets, useStatus } from "../api/hooks";
import type { AssetInfo } from "../api/types";
import { Sketch } from "../components/Sketch";
import { Button, ErrorNote } from "../components/ui";
import { useI18n, type Locale } from "../i18n";
import { useTheme } from "../theme";

export function Settings() {
  const { t, locale, setLocale } = useI18n();
  const { theme, setTheme } = useTheme();
  const { data: status, error } = useStatus();
  const openFolder = useMutation({ mutationFn: () => api.openFolder() });

  const gpu = status?.gpu;
  const claude = status?.claude;

  return (
    <div className="page settings">
      <header className="page-head">
        <h1 className="page-title">{t("settings.title")}</h1>
      </header>
      <ErrorNote error={error} />

      <section aria-labelledby="status-heading">
        <h2 id="status-heading" className="section-title">{t("settings.status")}</h2>
        <ul className="status-list">
          <StatusItem icon={gpu?.cuda ? "ok" : "warn"} title={t("settings.gpu")}
                      text={!gpu ? t("common.loading")
                        : gpu.cuda ? t("settings.gpuOk", { name: gpu.name ?? "", vram: gpu.vram_gb ?? "" })
                        : t("settings.gpuCpu")} />
          <StatusItem icon={!claude ? "wait" : claude.logged_in ? "ok" : "warn"} title="Claude Code"
                      text={!claude ? t("common.loading")
                        : !claude.installed ? t("settings.claudeMissing")
                        : claude.logged_in ? t("settings.claudeOk", { version: claude.version ?? "", plan: claude.subscription ?? "" })
                        : t("settings.claudeLogin")} />
          <StatusItem icon="info" title={t("settings.dataHome")} text={status?.data_home ?? ""}
                      action={<Button size="sm" variant="quiet" onClick={() => openFolder.mutate()}>{t("series.openFolder")}</Button>} />
          <StatusItem icon="info" title={t("settings.models")} text={status?.models_dir ?? ""} />
          <StatusItem icon="info" title={t("settings.version")} text={status ? `Yomitoki ${status.version}` : ""} />
        </ul>
      </section>

      <section aria-labelledby="look-heading">
        <h2 id="look-heading" className="section-title">{t("settings.appearance")}</h2>
        <ul className="status-list">
          <li className="status-item">
            <span className="status-item__icon" data-icon="moon" aria-hidden="true" />
            <div className="status-item__body">
              <p className="status-item__title">{t("settings.nightMode")}</p>
              <p className="muted">{t("settings.nightModeHint")}</p>
            </div>
            <label className="switch">
              <input type="checkbox" checked={theme === "night"} onChange={(e) => setTheme(e.target.checked ? "night" : "light")} />
              <span className="switch__track" aria-hidden="true" />
              <span className="visually-hidden">{t("settings.nightMode")}</span>
            </label>
          </li>
          <li className="status-item">
            <span className="status-item__icon" data-icon="lang" aria-hidden="true" />
            <div className="status-item__body">
              <p className="status-item__title">{t("settings.language")}</p>
              <p className="muted">{t("settings.languageHint")}</p>
            </div>
            <select className="input input--sm" value={locale} onChange={(e) => setLocale(e.target.value as Locale)}
                    aria-label={t("settings.language")}>
              <option value="zh-TW">繁體中文</option>
              <option value="en">English</option>
            </select>
          </li>
        </ul>
      </section>

      <AssetsSection />
    </div>
  );
}

function StatusItem({ icon, title, text, action }: { icon: "ok" | "warn" | "info" | "wait"; title: string; text: string; action?: ReactNode }) {
  return (
    <li className="status-item">
      <span className="status-item__icon" data-icon={icon} aria-hidden="true" />
      <div className="status-item__body">
        <p className="status-item__title">{title}</p>
        <p className="muted status-item__text">{text}</p>
      </div>
      {action}
    </li>
  );
}

function AssetsSection() {
  const { t } = useI18n();
  const { data, error } = useAssets();
  return (
    <section aria-labelledby="assets-heading">
      <h2 id="assets-heading" className="section-title">{t("settings.assets")}</h2>
      <p className="muted">{t("settings.assetsLead")}</p>
      <ErrorNote error={error} />
      <ul className="asset-grid">
        {data?.map((a) => <li key={a.id}><AssetCard asset={a} /></li>)}
      </ul>
    </section>
  );
}

function AssetCard({ asset }: { asset: AssetInfo }) {
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const onDone = (list: AssetInfo[]) => qc.setQueryData(keys.assets, list);
  const replace = useMutation({ mutationFn: (f: File) => api.replaceAsset(asset.id, f), onSuccess: onDone });
  const restore = useMutation({ mutationFn: () => api.restoreAsset(asset.id), onSuccess: onDone });
  const [w, h] = asset.size;

  return (
    <Sketch className="card asset-card" radius={18}>
      <div className={`asset-card__preview ${asset.background === "transparent" ? "is-transparent" : ""}`}>
        <img src={asset.url} alt={asset.purpose} loading="lazy" />
      </div>
      <p className="asset-card__id"><code>{asset.id}</code>
        <span className={`badge badge--${asset.source}`}>{t(`settings.source_${asset.source}`)}</span>
      </p>
      <p className="small">{locale === "zh-TW" ? asset.purpose : asset.purpose_en}</p>
      <p className="muted small">
        {t("settings.recommended", { w, h, w2: w * 2, h2: h * 2 })}
        {asset.background === "transparent" ? ` · ${t("settings.transparent")}` : ""}
      </p>
      {asset.warnings.map((warn) => <p key={warn} className="warn small">{warn}</p>)}
      <input ref={input} type="file" accept=".svg,.png,.webp,image/svg+xml,image/png,image/webp" hidden
             onChange={(e) => { const f = e.target.files?.[0]; if (f) replace.mutate(f); e.target.value = ""; }} />
      <div className="asset-card__actions">
        <Button size="sm" onClick={() => input.current?.click()} disabled={replace.isPending}>{t("settings.replace")}</Button>
        {asset.source === "custom" && (
          <Button size="sm" variant="quiet" onClick={() => restore.mutate()} disabled={restore.isPending}>{t("settings.restore")}</Button>
        )}
      </div>
      <ErrorNote error={replace.error ?? restore.error} />
    </Sketch>
  );
}
