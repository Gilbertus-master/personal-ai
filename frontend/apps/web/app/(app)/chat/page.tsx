'use client';

import { useEffect } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';

/**
 * /chat — clears active conversation so the layout shows empty state.
 */
export default function ChatPage() {
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);

  useEffect(() => {
    setActiveConversation(null);
  }, [setActiveConversation]);

  return null;
}
