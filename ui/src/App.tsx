import { useEffect } from "react";
import { Link, Route, Switch, useLocation } from "wouter";
import { useAssetUrl } from "./api/hooks";
import { useI18n } from "./i18n";
import { GlossaryPage } from "./pages/Glossary";
import { Reader } from "./pages/Reader";
import { SeriesPage } from "./pages/Series";
import { Settings } from "./pages/Settings";
import { Shelf } from "./pages/Shelf";
import { useTheme } from "./theme";

function Header() {
  const { t, locale, setLocale } = useI18n();
  const { theme, setTheme } = useTheme();
  const [location] = useLocation();
  const icon = useAssetUrl("app-icon");
  return (
    <header className="topbar">
      <Link href="/" className="brand">
        <img src={icon} alt="" className="brand__icon" />
        <span className="brand__name">Yomitoki</span>
        <span className="brand__sub">{t("app.tagline")}</span>
      </Link>
      <nav className="topbar__nav" aria-label={t("nav.label")}>
        <Link href="/" className={`navlink ${location === "/" ? "is-active" : ""}`}>{t("nav.shelf")}</Link>
        <Link href="/settings" className={`navlink ${location === "/settings" ? "is-active" : ""}`}>{t("nav.settings")}</Link>
      </nav>
      <div className="topbar__tools">
        <button type="button" className="chip" onClick={() => setTheme(theme === "night" ? "light" : "night")}
                aria-pressed={theme === "night"}>
          {theme === "night" ? t("theme.light") : t("theme.night")}
        </button>
        <button type="button" className="chip" onClick={() => setLocale(locale === "zh-TW" ? "en" : "zh-TW")}>
          {locale === "zh-TW" ? "English" : "繁體中文"}
        </button>
      </div>
    </header>
  );
}

/** 背景紙紋也是可替換素材；換圖後網址帶新版本號，這裡同步到 CSS 變數。 */
function PaperTexture() {
  const url = useAssetUrl("paper-texture");
  useEffect(() => {
    document.documentElement.style.setProperty("--paper-url", `url("${url}")`);
  }, [url]);
  return null;
}

export function App() {
  return (
    <>
      <PaperTexture />
      <Switch>
        <Route path="/read/:name/:ep/:page?" component={Reader} />
        <Route>
          <Header />
          <main className="main">
            <Switch>
              <Route path="/" component={Shelf} />
              <Route path="/series/:name/glossary" component={GlossaryPage} />
              <Route path="/series/:name" component={SeriesPage} />
              <Route path="/settings" component={Settings} />
              <Route><NotFound /></Route>
            </Switch>
          </main>
        </Route>
      </Switch>
    </>
  );
}

function NotFound() {
  const { t } = useI18n();
  return (
    <div className="empty">
      <h2 className="empty__title">{t("errors.notFound")}</h2>
      <Link href="/" className="navlink">{t("nav.backToShelf")}</Link>
    </div>
  );
}
