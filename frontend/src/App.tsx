import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router-dom";
import type { Lang } from "./api/types";
import Disclaimer from "./components/common/Disclaimer";
import { ConfigProvider } from "./lib/config";
import Landing from "./pages/Landing";
import Methodology from "./pages/Methodology";
import Retro from "./pages/Retro";
import Wizard from "./pages/Wizard";

function LangSwitch() {
  const { t, i18n } = useTranslation();
  return (
    <div role="group" aria-label={t("app.lang.switch")} className="flex overflow-hidden rounded-xl border-2 border-white/70">
      {(["ru", "kk"] as Lang[]).map((l) => (
        <button
          key={l}
          type="button"
          onClick={() => void i18n.changeLanguage(l)}
          aria-pressed={i18n.language === l}
          className={`min-h-[40px] px-3 font-bold ${i18n.language === l ? "bg-white text-field-800" : "text-white hover:bg-white/10"}`}
        >
          {t(`app.lang.${l}`)}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const { t } = useTranslation();
  const link = ({ isActive }: { isActive: boolean }) =>
    `whitespace-nowrap rounded-lg px-3 py-2 font-semibold no-underline ${isActive ? "bg-white text-field-800" : "text-white hover:bg-white/10"}`;
  return (
    <ConfigProvider>
      <div className="flex min-h-screen flex-col">
        <header className="bg-field-800 text-white">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <NavLink to="/" className="flex items-center gap-2 text-xl font-bold text-white no-underline">
              <img src="/favicon.svg" alt="" className="h-8 w-8" />
              {t("app.name")}
            </NavLink>
            <LangSwitch />
          </div>
          <nav className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 pb-2">
            <NavLink to="/" end className={link}>{t("app.nav.home")}</NavLink>
            <NavLink to="/field" className={link}>{t("app.nav.wizard")}</NavLink>
            <NavLink to="/retro" className={link}>{t("app.nav.retro")}</NavLink>
            <NavLink to="/methodology" className={link}>{t("app.nav.methodology")}</NavLink>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/field" element={<Wizard />} />
            <Route path="/retro" element={<Retro />} />
            <Route path="/methodology" element={<Methodology />} />
            <Route path="*" element={<Landing />} />
          </Routes>
        </main>
        <footer className="sticky bottom-0 z-[1000] border-t border-wheat-300 bg-wheat-100">
          <div className="mx-auto max-w-6xl">
            <Disclaimer compact />
          </div>
        </footer>
        <div className="bg-field-900 px-4 py-3 text-center text-xs text-field-100">{t("app.footer")}</div>
      </div>
    </ConfigProvider>
  );
}
