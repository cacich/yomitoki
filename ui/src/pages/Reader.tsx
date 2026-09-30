import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import { Link, useLocation, useParams } from "wouter";
import { useEpisode, useSeries, useStatus } from "../api/hooks";
import { AssetImage, ErrorNote } from "../components/ui";
import { useI18n } from "../i18n";

const IDLE_MS = 2500;

export function Reader() {
  const params = useParams<{ name: string; ep: string; page?: string }>();
  const name = decodeURIComponent(params.name);
  const { t } = useI18n();
  const [, navigate] = useLocation();
  const { data: ep, error } = useEpisode(name, params.ep);
  const { data: series } = useSeries(name);
  const { data: status } = useStatus();

  const pages = ep?.pages_detail ?? [];
  const index = Math.max(0, params.page ? pages.findIndex((p) => p.stem === params.page) : 0);
  const page = pages[index];

  const rtl = useMemo(() => {
    const src = series?.settings.source_lang;
    return status?.languages.sources.find((l) => l.code === src)?.reading_rtl ?? true;
  }, [series, status]);

  const [showOriginal, setShowOriginal] = useState(false); // 工具列切換（固定）
  const [holding, setHolding] = useState(false);            // 按住空白鍵（暫時）
  const [idle, setIdle] = useState(false);
  const idleTimer = useRef<number | undefined>(undefined);

  const seriesHref = `/series/${encodeURIComponent(name)}`;
  const go = useCallback(
    (delta: number) => {
      const next = pages[index + delta];
      if (next) navigate(`/read/${encodeURIComponent(name)}/${params.ep}/${next.stem}`, { replace: true });
    },
    [pages, index, name, params.ep, navigate],
  );

  // 右翻書（日漫）：← 是下一頁；左翻書：→ 是下一頁
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === " ") {
        e.preventDefault();
        setHolding(e.type === "keydown");
        return;
      }
      if (e.type !== "keydown") return;
      if (e.key === "ArrowLeft") go(rtl ? 1 : -1);
      else if (e.key === "ArrowRight") go(rtl ? -1 : 1);
      else if (e.key === "Escape") navigate(seriesHref);
      else if (e.key.toLowerCase() === "o") setShowOriginal((v) => !v);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("keyup", onKey);
    };
  }, [go, rtl, navigate, seriesHref]);

  // 滑鼠停著不動時收起工具列，讓畫面只剩漫畫
  useEffect(() => {
    const wake = () => {
      setIdle(false);
      window.clearTimeout(idleTimer.current);
      idleTimer.current = window.setTimeout(() => setIdle(true), IDLE_MS);
    };
    wake();
    window.addEventListener("mousemove", wake);
    return () => {
      window.removeEventListener("mousemove", wake);
      window.clearTimeout(idleTimer.current);
    };
  }, []);

  // 預先載入前後頁
  useEffect(() => {
    [pages[index - 1], pages[index + 1]].forEach((p) => {
      if (p) new Image().src = p.translated ?? p.original;
    });
  }, [pages, index]);

  const onClickImage = (e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const leftHalf = e.clientX - rect.left < rect.width / 2;
    go(leftHalf === rtl ? 1 : -1);
  };

  if (error) return <div className="reader"><ErrorNote error={error} /></div>;
  if (!ep) {
    return (
      <div className="reader reader--loading">
        <AssetImage id="mascot-loading" className="reader__loading" />
      </div>
    );
  }
  if (!page) {
    return (
      <div className="reader reader--loading">
        <p>{t("reader.noPages")}</p>
        <Link href={seriesHref}>{t("reader.back")}</Link>
      </div>
    );
  }

  const original = showOriginal !== holding; // 按住空白鍵時暫時切到另一邊
  const src = original || !page.translated ? page.original : page.translated;

  return (
    <div className={`reader ${idle ? "is-idle" : ""}`}>
      <div className="reader__stage" onClick={onClickImage}>
        <img key={src} src={src} alt={t("reader.pageAlt", { n: index + 1 })} className="reader__image" draggable={false} />
      </div>

      <div className="reader__toolbar" role="toolbar" aria-label={t("reader.toolbar")}>
        <Link href={seriesHref} className="reader__btn">{t("reader.back")}</Link>
        <span className="reader__count">{index + 1} / {pages.length}</span>
        <button type="button" className="reader__btn" onClick={() => setShowOriginal((v) => !v)} aria-pressed={showOriginal}
                disabled={!page.translated}>
          {showOriginal ? t("reader.showTranslation") : t("reader.showOriginal")}
        </button>
      </div>

      <div className="reader__hint">
        {!page.translated ? t("reader.notTranslated") : original ? t("reader.viewingOriginal") : t("reader.holdHint")}
      </div>
    </div>
  );
}
