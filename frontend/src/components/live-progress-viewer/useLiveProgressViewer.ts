import { useState, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { ProgressMessage, ProgressBarMessage } from './types';

/**
 * Hook encapsulating all state and helpers for the live progress viewer.
 */
export function useLiveProgressViewer() {
  const [progressMessages, setProgressMessages] = useState<
    Map<string, ProgressMessage>
  >(new Map());
  const containerRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom whenever we add/remove messages
  useEffect(() => {
    const el = containerRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }
  }, [progressMessages.size]);

  const clearProgressMessages = () => {
    setProgressMessages(() => new Map());
  };

  const addProgressMessage = (message: ProgressMessage): string => {
    const id = uuidv4();
    setProgressMessages(prev => {
      const next = new Map(prev);
      next.set(id, message);
      return next;
    });
    return id;
  };

  const deleteProgressMessageById = (id: string) => {
    setProgressMessages(prev => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
  };

  const replaceMessageById = (
    id: string,
    newMessage: ProgressMessage
  ) => {
    setProgressMessages(prev => {
      const next = new Map(prev);
      next.set(id, newMessage);
      return next;
    });
  };

  const updateMessageById = (
    id: string,
    callback: (previous: ProgressMessage) => ProgressMessage
  ) => {
    setProgressMessages(prev => {
      const next = new Map(prev);
      const existing = next.get(id);
      if (!existing) return prev;
      next.set(id, callback(existing));
      return next;
    });
  };

  const upsertProgressBarByTitle = (
    title: string,
    current: number,
    max: number,
    defaultOptions: Omit<ProgressBarMessage,"title"|"current"|"max"|"kind">
  ): string => {
    let targetId: string | null = null;
    
    // Find existing progress bar with matching title
    for (const [id, message] of progressMessages.entries()) {
      if (message.kind === 'progressBar' && message.title === title) {
        targetId = id;
        break;
      }
    }
    

    const newMessage: ProgressBarMessage = {
      ...defaultOptions,
      title,
      current,
      max,
      kind: 'progressBar',
    }

    if (targetId) {
      // Update existing progress bar
      setProgressMessages(prev => {
        const next = new Map(prev);
        next.set(targetId!, newMessage);
        return next;
      });
      return targetId;
    } else {
      // Create new progress bar
      const newId = uuidv4();
      setProgressMessages(prev => {
        const next = new Map(prev);
        next.set(newId, newMessage);
        return next;
      });
      return newId;
    }
  };

  return {
    progressMessages,
    containerRef,
    addProgressMessage,
    deleteProgressMessageById,
    replaceMessageById,
    updateMessageById,
    upsertProgressBarByTitle,
    clearProgressMessages,
  };
}