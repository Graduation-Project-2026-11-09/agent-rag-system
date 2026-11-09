const pad = (n) => String(n).padStart(2, '0');

export function formatDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())}`;
}

export function formatRelative(iso) {
  const diff = (Date.now() - Date.parse(iso)) / 60000;
  if (diff < 1) return 'たった今';
  if (diff < 60) return `${Math.floor(diff)}分前`;
  if (diff < 60 * 24) return `${Math.floor(diff / 60)}時間前`;
  if (diff < 60 * 24 * 7) return `${Math.floor(diff / 1440)}日前`;
  return formatDate(iso);
}

export function formatFileSize(bytes) {
  if (!bytes) return '—';
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export const formatPercent = (v) => `${Math.round(v * 100)}%`;

// <input type="datetime-local"> 用
export function toLocalInput(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function visibilityLabel(v) {
  return v.type === 'all' ? '全社公開' : v.departments.join('・');
}
