'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useChatStore } from '@/lib/stores/chat-store';

/**
 * /chat/[id] — activates the conversation matching the URL param.
 * Redirects to /chat if the conversation doesn't exist.
 */
export function PageClient() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const conversations = useChatStore((s) => s.conversations);
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);

  useEffect(() => {
    const exists = conversations.some((c) => c.id === id);
    if (exists) {
      setActiveConversation(id);
    } else {
      router.replace('/chat');
    }
  }, [id, conversations, setActiveConversation, router]);

  return null;
}
