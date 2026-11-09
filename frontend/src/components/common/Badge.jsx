/** tone: gray | green | blue | yellow | red */
export default function Badge({ tone = 'gray', children }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

/** constants.js のラベル定義からバッジを表示する */
export function StatusBadge({ map, value }) {
  const def = map[value];
  if (!def) return null;
  return <Badge tone={def.tone}>{def.label}</Badge>;
}
