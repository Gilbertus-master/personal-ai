'use client';

import { useMemo } from 'react';
import { useChat } from '@/lib/hooks/use-chat';
import { useChatStore, selectActiveConversation } from '@/lib/stores/chat-store';
import type { ChatMessage } from '@/lib/stores/chat-store';
import {
  ChatSidebar,
  ChatHeader,
  ChatInput,
  MessageList,
  EmptyState,
} from '@gilbertus/ui';
import type { MessageBubbleMessage } from '@gilbertus/ui';

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  const {
    conversations,
    activeConversationId,
    setActiveConversation,
    deleteConversation,
    renameConversation,
    sendMessage,
    handleQuickAction,
  } = useChat();

  const activeConv = useChatStore(selectActiveConversation);

  // Map store messages to UI's MessageBubbleMessage (different SourceItem shape)
  const mappedMessages: MessageBubbleMessage[] = useMemo(() => {
    if (!activeConv) return [];
    return activeConv.messages.map((msg: ChatMessage) => ({
      ...msg,
      sources: msg.sources?.map((s) => ({
        document_id: 0,
        title: s.content,
        source_type: s.source_type,
        source_name: s.source_name,
        created_at: s.date ?? '',
      })),
    }));
  }, [activeConv]);

  const handleNewChat = () => {
    setActiveConversation(null);
  };

  const handleSend = async (text: string) => {
    await sendMessage(text);
  };

  return (
    <div className="-m-6 flex h-[calc(100%+3rem)]">
      {/* children sets activeConversationId — renders nothing visible */}
      {children}

      {/* Left sidebar */}
      <ChatSidebar
        conversations={conversations}
        activeId={activeConversationId}
        onSelect={(id) => setActiveConversation(id)}
        onNew={handleNewChat}
        onDelete={deleteConversation}
        onRename={renameConversation}
      />

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {activeConv ? (
          <>
            <ChatHeader
              title={activeConv.title}
              onRename={(t) => renameConversation(activeConv.id, t)}
            />
            <MessageList
              messages={mappedMessages}
              onRetry={() => {
                /* retry not yet implemented */
              }}
            />
            <ChatInput
              onSend={handleSend}
              onQuickAction={handleQuickAction}
              disabled={activeConv.messages.some((m) => m.isLoading)}
            />
          </>
        ) : (
          <div className="flex flex-1 flex-col">
            <div className="flex flex-1 items-center justify-center">
              <EmptyState onQuickAction={handleQuickAction} />
            </div>
            <ChatInput
              onSend={handleSend}
              onQuickAction={handleQuickAction}
              placeholder="Zadaj pytanie Gilbertusowi..."
            />
          </div>
        )}
      </div>
    </div>
  );
}
