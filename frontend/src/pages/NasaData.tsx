import { ArrowRight, CheckCircle2, CircleDashed, ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Lang } from "../api/types";
import { ErrorBox, Loading, Notice, PageHeader, SectionTitle } from "../components/ui/ui";
import { errorText, useAsync } from "../lib/async";
import { tx } from "../lib/i18n-text";

const DEMO_STEPS = ["select", "environment", "history", "compare", "priorities", "drought", "explain", "export"] as const;

export default function NasaData() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language as Lang;
  const rules = useAsync(() => api.rules(), []);
  return (
    <div className="space-y-10">
      <PageHeader eyebrow={t("nasa.eyebrow")} title={t("nasa.title")} subtitle={t("nasa.subtitle")} />

      <section className="grid gap-6 lg:grid-cols-3">
        {(["problem", "approach", "data"] as const).map((k) => (
          <div key={k} className="panel p-5">
            <h2 className="h3">{t(`nasa.pitch.${k}_title`)}</h2>
            <p className="mt-2 text-sm leading-relaxed text-ink-2">{t(`nasa.pitch.${k}`)}</p>
          </div>
        ))}
      </section>

      <section>
        <SectionTitle title={t("nasa.datasets_title")} hint={t("nasa.datasets_hint")} />
        {rules.error ? <ErrorBox message={errorText(rules.error, t)} onRetry={rules.reload} /> : null}
        {!rules.data && !rules.error && <Loading />}
        {rules.data && (
          <div className="space-y-3">
            {rules.data.data_sources.map((d) => {
              const integrated = d.status === "active";
              return (
                <article key={d.id} className="panel">
                  <div className="panel-head">
                    <div className="min-w-0">
                      <h3 className="h3">{d.title}</h3>
                      <div className="text-xs text-ink-muted">{d.provider}</div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {integrated ? (
                        <span className="badge-green"><CheckCircle2 className="h-3.5 w-3.5" /> {t("nasa.integrated")}</span>
                      ) : (
                        <span className="badge-neutral"><CircleDashed className="h-3.5 w-3.5" /> {t("nasa.not_integrated")}</span>
                      )}
                      {integrated && d.state !== "active" && <span className="badge-amber">{t(`methodology.state.${d.state}`)}</span>}
                    </div>
                  </div>
                  <div className="panel-body grid gap-4 text-sm md:grid-cols-2 xl:grid-cols-4">
                    <div><div className="eyebrow mb-1">{t("methodology.used_for")}</div><p className="text-ink-2">{tx(d.used_for, lang)}</p></div>
                    <div><div className="eyebrow mb-1">{t("methodology.resolution")}</div><p className="text-ink-2">{tx(d.spatial_resolution, lang)}</p></div>
                    <div><div className="eyebrow mb-1">{t("methodology.coverage")}</div><p className="text-ink-2">{tx(d.temporal_coverage, lang)}</p></div>
                    <div><div className="eyebrow mb-1">{t("methodology.limitations")}</div><p className="text-ink-2">{tx(d.limitations, lang)}</p></div>
                    <div className="md:col-span-2 xl:col-span-4 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-3 text-xs text-ink-muted">
                      <span>{tx(d.provenance, lang)}</span>
                      <a href={d.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1">{t("nasa.docs")} <ExternalLink className="h-3 w-3" /></a>
                      {d.doi && <a href={d.doi} target="_blank" rel="noreferrer">DOI</a>}
                      <span>{t("methodology.checked")}: {d.checked}</span>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="panel p-5">
          <h2 className="h3">{t("nasa.honest_title")}</h2>
          <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-ink-2">
            {[1, 2, 3, 4, 5].map((i) => <li key={i}>{t(`nasa.honest_${i}`)}</li>)}
          </ul>
        </div>
        <div className="panel p-5">
          <h2 className="h3">{t("nasa.demo_title")}</h2>
          <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm text-ink-2">
            {DEMO_STEPS.map((s) => <li key={s}>{t(`nasa.demo.${s}`)}</li>)}
          </ol>
          <Link to="/demo" className="btn-primary mt-4 no-underline">{t("landing2.cta_demo")} <ArrowRight className="h-4 w-4" /></Link>
        </div>
      </section>
      <Notice>{t("nasa.affiliation")}</Notice>
    </div>
  );
}
