import { useState } from 'react';
import { Copy, ThumbsUp, ThumbsDown, Sparkles } from 'lucide-react';
import AgentTrace from './AgentTrace';
import MessageContent from './MessageContent';
import SourceList from './SourceList';
import NextSteps from './NextSteps';
import InquirySuggestion from './InquirySuggestion';
import { useToast } from '../../contexts/ToastContext';

export default function AssistantMessage({ message, onOpenSource, onFeedback, onCreateInquiry }) {
  const toast = useToast();
  const [dismissed, setDismissed] = useState(false);
  const openByIndex = (i) => {
    const s = message.sources.find((x) => x.index === i);
    if (s) onOpenSource(s);
  };

  return (
    <div className="msg msg-assistant">
      <span className="msg-avatar"><Sparkles size={14} /></span>
      <div className="msg-body">
        <AgentTrace steps={message.agent.steps} searchCount={message.agent.searchCount} durationMs={message.agent.durationMs} running={false} />
        <MessageContent content={message.content} onCite={openByIndex} />
        <SourceList sources={message.sources} onOpen={onOpenSource} />
        <NextSteps steps={message.nextSteps} />
        {message.inquirySuggestion && (
          <InquirySuggestion
            suggestion={message.inquirySuggestion}
            inquiryId={message.inquiryId}
            dismissed={dismissed}
            onDismiss={() => setDismissed(true)}
            onCreate={onCreateInquiry}
          />
        )}
        <div className="msg-actions">
          <button
            className="icon-btn"
            title="コピー"
            onClick={() => navigator.clipboard?.writeText(message.content).then(() => toast('回答をコピーしました'))}
          >
            <Copy size={15} />
          </button>
          <button className={`icon-btn ${message.feedback === 'good' ? 'active' : ''}`} title="役に立った" onClick={() => onFeedback('good')}>
            <ThumbsUp size={15} />
          </button>
          <button className={`icon-btn ${message.feedback === 'bad' ? 'active' : ''}`} title="役に立たなかった" onClick={() => onFeedback('bad')}>
            <ThumbsDown size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
