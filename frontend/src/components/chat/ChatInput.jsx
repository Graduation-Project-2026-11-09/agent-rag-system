import { useEffect, useRef, useState } from 'react';
import { ArrowUp, Square } from 'lucide-react';

export default function ChatInput({ onSend, onStop, busy, autoFocus }) {
  const [text, setText] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  const submit = () => {
    const v = text.trim();
    if (!v || busy) return;
    onSend(v);
    setText('');
  };

  return (
    <div className="chat-input-wrap">
      <div className="chat-input">
        <textarea
          ref={ref}
          rows={1}
          value={text}
          placeholder="社内の制度や手続きについて質問してください"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
        />
        {busy ? (
          <button className="send-btn" onClick={onStop} aria-label="停止"><Square size={14} fill="currentColor" /></button>
        ) : (
          <button className="send-btn" onClick={submit} disabled={!text.trim()} aria-label="送信"><ArrowUp size={18} /></button>
        )}
      </div>
      <p className="input-note">AIの回答は誤りを含む可能性があります。重要な内容は根拠資料で確認してください。</p>
    </div>
  );
}
