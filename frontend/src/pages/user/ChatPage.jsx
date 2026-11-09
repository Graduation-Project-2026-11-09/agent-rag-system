import { useEffect, useRef, useState } from 'react';
import { useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { chatApi } from '../../api';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../contexts/ToastContext';
import ChatInput from '../../components/chat/ChatInput';
import AgentTrace from '../../components/chat/AgentTrace';
import AssistantMessage from '../../components/chat/AssistantMessage';
import SourcePreviewModal from '../../components/chat/SourcePreviewModal';
import InquiryModal from '../../components/chat/InquiryModal';
import Spinner from '../../components/common/Spinner';
import { SUGGESTED_QUESTIONS } from '../../constants';

export default function ChatPage() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const { reloadConversations } = useOutletContext();
  const { user } = useAuth();
  const toast = useToast();

  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState(null); // 回答生成中の Agent ステップ
  const [source, setSource] = useState(null);
  const [inquiryTarget, setInquiryTarget] = useState(null);
  const abortRef = useRef(null);
  const createdIdRef = useRef(null); // 新規作成直後の会話は再読み込みしない
  const bottomRef = useRef(null);

  useEffect(() => {
    if (conversationId && conversationId === createdIdRef.current) {
      createdIdRef.current = null;
      return;
    }
    abortRef.current?.abort();
    setPending(null);
    if (!conversationId) {
      setMessages([]);
      return;
    }
    setLoading(true);
    chatApi
      .getConversation(conversationId)
      .then((c) => setMessages(c.messages))
      .catch(() => navigate('/chat', { replace: true }))
      .finally(() => setLoading(false));
  }, [conversationId, navigate]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, pending?.steps.length]);

  const send = async (text) => {
    let id = conversationId;
    if (!id) {
      const c = await chatApi.createConversation(text);
      id = c.id;
      createdIdRef.current = id;
      navigate(`/chat/${id}`);
      reloadConversations();
    }
    setMessages((m) => [...m, { id: `tmp-${Date.now()}`, role: 'user', content: text, createdAt: new Date().toISOString() }]);
    setPending({ steps: [] });
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await chatApi.sendMessage(
        id,
        text,
        (ev) => {
          if (ev.type === 'step') setPending((p) => p && { steps: [...p.steps, ev.data] });
          if (ev.type === 'answer') {
            setMessages((m) => [...m, ev.data]);
            setPending(null);
          }
          if (ev.type === 'error') throw new Error(ev.data.message);
        },
        controller.signal,
      );
    } catch (e) {
      if (e.name !== 'AbortError') toast(e.message ?? '回答の取得に失敗しました', 'error');
      setPending(null);
    } finally {
      reloadConversations();
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    setPending(null);
    toast('回答の生成を停止しました', 'error');
  };

  const updateMessage = (id, patch) => setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...patch } : m)));

  const feedback = (m, value) => {
    const next = m.feedback === value ? null : value;
    updateMessage(m.id, { feedback: next });
    chatApi.sendFeedback(m.id, next);
    if (next) toast('フィードバックありがとうございます');
  };

  const questionFor = (m) => {
    const i = messages.indexOf(m);
    return messages.slice(0, i).reverse().find((x) => x.role === 'user')?.content ?? '';
  };

  const isEmpty = !messages.length && !pending && !loading;

  return (
    <div className="chat-page">
      <div className="chat-scroll">
        {loading && <Spinner />}
        {isEmpty ? (
          <div className="chat-welcome">
            <span className="brand-mark lg"><Sparkles size={26} /></span>
            <h2>{user.name.split(' ')[1] ?? user.name}さん、何をお調べしますか？</h2>
            <p className="muted">社内規程・手続きマニュアルなどをAIが検索し、根拠資料とあわせて回答します。</p>
            <div className="suggest-grid">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button key={q} className="suggest-card" onClick={() => send(q)}>{q}</button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-thread">
            {messages.map((m) =>
              m.role === 'user' ? (
                <div key={m.id} className="msg msg-user">
                  <div className="bubble">{m.content}</div>
                </div>
              ) : (
                <AssistantMessage
                  key={m.id}
                  message={m}
                  onOpenSource={setSource}
                  onFeedback={(v) => feedback(m, v)}
                  onCreateInquiry={() => setInquiryTarget(m)}
                />
              ),
            )}
            {pending && (
              <div className="msg msg-assistant">
                <span className="msg-avatar"><Sparkles size={14} /></span>
                <div className="msg-body">
                  <AgentTrace steps={pending.steps} running />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <ChatInput onSend={send} onStop={stop} busy={!!pending} autoFocus={!conversationId} />

      {source && <SourcePreviewModal source={source} onClose={() => setSource(null)} />}
      {inquiryTarget && (
        <InquiryModal
          message={inquiryTarget}
          question={questionFor(inquiryTarget)}
          onClose={() => setInquiryTarget(null)}
          onSent={(inq) => updateMessage(inquiryTarget.id, { inquiryId: inq.id })}
        />
      )}
    </div>
  );
}
