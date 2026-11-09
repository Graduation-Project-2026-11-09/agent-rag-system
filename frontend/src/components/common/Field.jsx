export default function Field({ label, required, hint, error, children }) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {required && <span className="required">必須</span>}
      </span>
      {children}
      {error ? <span className="field-error">{error}</span> : hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}
