import React from 'react';
import Panel from './Panel';

function messageTone(message) {
  if (message.includes('ERROR')) return 'tone-red';
  if (message.includes('SELL')) return 'tone-green';
  if (message.includes('BUY')) return 'tone-yellow';
  return 'tone-blue';
}

export default function MessagePanel({ messages }) {
  return (
    <Panel title="상태 메시지" subtitle="실행 로그">
      <div className="message-list">
        {messages.map((message) => (
          <div key={message} className={`message-row ${messageTone(message)}`}>
            <span className="message-dot" />
            <span>{message}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}
