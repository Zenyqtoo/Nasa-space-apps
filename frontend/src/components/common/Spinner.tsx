export default function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-field-800" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-4 border-field-200 border-t-field-700" />
      {label && <span>{label}</span>}
    </div>
  );
}
