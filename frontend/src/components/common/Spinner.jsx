import { Loader2 } from 'lucide-react';

export default function Spinner({ label = '読み込み中…' }) {
  return (
    <div className="spinner-wrap">
      <Loader2 className="spin" size={20} />
      <span>{label}</span>
    </div>
  );
}
