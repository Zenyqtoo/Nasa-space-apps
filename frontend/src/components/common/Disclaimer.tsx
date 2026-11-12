import { useTranslation } from "react-i18next";

export default function Disclaimer({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  return (
    <div
      role="note"
      className={`border-l-4 border-wheat-500 bg-wheat-100 font-semibold text-soil-900 ${compact ? "px-3 py-2 text-sm" : "rounded-xl px-4 py-3"}`}
    >
      ⚠️ {t("app.disclaimer")}
    </div>
  );
}
