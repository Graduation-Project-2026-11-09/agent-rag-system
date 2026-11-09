// 資料・お知らせの公開範囲（全社 / 部署指定）を編集する
export default function VisibilityEditor({ value, onChange, departments, allLabel = '全社公開' }) {
  const toggle = (dep) => {
    const set = new Set(value.departments ?? []);
    set.has(dep) ? set.delete(dep) : set.add(dep);
    onChange({ type: 'departments', departments: [...set] });
  };
  return (
    <div className="visibility-editor">
      <div className="radio-row">
        <label className="radio">
          <input type="radio" checked={value.type === 'all'} onChange={() => onChange({ type: 'all' })} />
          {allLabel}
        </label>
        <label className="radio">
          <input type="radio" checked={value.type === 'departments'} onChange={() => onChange({ type: 'departments', departments: value.departments ?? [] })} />
          部署を指定
        </label>
      </div>
      {value.type === 'departments' && (
        <div className="chip-select">
          {departments.map((d) => (
            <button type="button" key={d} className={`chip ${value.departments?.includes(d) ? 'chip-on' : ''}`} onClick={() => toggle(d)}>
              {d}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
