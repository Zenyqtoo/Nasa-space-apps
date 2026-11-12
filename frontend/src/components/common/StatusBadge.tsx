import { useTranslation } from "react-i18next";
import type { Status } from "../../api/types";

/** Значок «требует проверки» для значений со статусом assumption. */
export default function StatusBadge({ status }: { status: Status }) {
  const { t } = useTranslation();
  if (status === "verified") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-field-100 px-2 py-0.5 text-xs font-semibold text-field-800">
        ✓ {t("app.verified")}
      </span>
    );
  }
  return (
    <span
      title={t("app.needs_check_title")}
      className="inline-flex items-center gap-1 rounded-full border border-amber-500 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-900"
    >
      ⚠ {t("app.needs_check")}
    </span>
  );
}
