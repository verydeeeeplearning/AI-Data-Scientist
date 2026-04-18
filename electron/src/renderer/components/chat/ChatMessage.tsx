/**
 * Single chat message with Markdown rendering.
 */

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Bot, User } from 'lucide-react';
import type { ChatMessage as ChatMessageType } from '../../stores/chatStore';
import { getBackendBase } from '../../utils/backendUrl';

interface Props {
  message: ChatMessageType;
  isStreaming?: boolean;
}

export function ChatMessage({ message, isStreaming }: Props) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 px-4 py-3 ${isUser ? 'bg-ds-surface/50' : ''}`}>
      {/* Avatar */}
      <div className={`
        flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center mt-0.5
        ${isUser ? 'bg-ds-accent/20 text-ds-accent' : 'bg-ds-success/20 text-ds-success'}
      `}>
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 overflow-hidden">
        <div className="text-xs text-ds-muted mb-1">
          {isUser ? 'You' : 'DS Agent'}
        </div>
        <div className="prose prose-invert prose-sm max-w-none
          prose-headings:text-ds-text prose-p:text-ds-text prose-li:text-ds-text
          prose-code:text-ds-accent prose-strong:text-ds-text
          prose-a:text-ds-accent prose-a:no-underline hover:prose-a:underline
          prose-table:text-ds-text prose-th:text-ds-text prose-td:text-ds-text
          prose-pre:bg-transparent prose-pre:p-0
        ">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                const code = String(children).replace(/\n$/, '');

                if (match) {
                  return (
                    <SyntaxHighlighter
                      style={oneDark}
                      language={match[1]}
                      PreTag="div"
                      customStyle={{
                        margin: '0.5rem 0',
                        borderRadius: '0.375rem',
                        fontSize: '0.8rem',
                      }}
                    >
                      {code}
                    </SyntaxHighlighter>
                  );
                }

                return (
                  <code className="bg-ds-surface px-1.5 py-0.5 rounded text-xs" {...props}>
                    {children}
                  </code>
                );
              },
              table({ children }) {
                return (
                  <div className="overflow-x-auto my-2">
                    <table className="border-collapse border border-ds-border text-sm">
                      {children}
                    </table>
                  </div>
                );
              },
              th({ children }) {
                return (
                  <th className="border border-ds-border bg-ds-surface px-3 py-1.5 text-left font-medium">
                    {children}
                  </th>
                );
              },
              td({ children }) {
                return (
                  <td className="border border-ds-border px-3 py-1.5">
                    {children}
                  </td>
                );
              },
              img({ src, alt }) {
                // 4.14 fix: Use dynamic backend URL instead of hardcoded port
                const plotSrc = src?.startsWith('http')
                  ? src
                  : `${getBackendBase()}/api/plots/${encodeURIComponent(src ?? '')}`;
                return (
                  <div className="my-2 rounded-lg overflow-hidden border border-ds-border inline-block">
                    <img
                      src={plotSrc}
                      alt={alt ?? 'Plot'}
                      className="max-w-full cursor-pointer"
                    />
                  </div>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
          {isStreaming && (
            <span className="inline-block w-2 h-4 bg-ds-accent animate-pulse ml-0.5" />
          )}
        </div>
      </div>
    </div>
  );
}
