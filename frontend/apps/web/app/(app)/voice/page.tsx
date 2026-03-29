'use client';

import { useVoice } from '@/lib/hooks/use-voice';
import { useVoiceHealth } from '@/lib/hooks/use-voice-health';
import { useVoiceStore } from '@/lib/stores/voice-store';
import {
  VoiceHeader,
  VoiceSessionList,
  VoiceConversation,
  VoiceControls,
  VoiceCommandBar,
} from '@gilbertus/ui';

export default function VoicePage() {
  const voice = useVoice();
  const { data: health, isLoading: healthLoading } = useVoiceHealth();
  const createSession = useVoiceStore((s) => s.createSession);

  const activeSession = voice.sessions.find((s) => s.id === voice.activeSessionId);
  const messages = activeSession?.messages ?? [];

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Left: Session history */}
      <div className="hidden w-64 shrink-0 lg:block">
        <VoiceSessionList
          sessions={voice.sessions}
          activeSessionId={voice.activeSessionId}
          onSelectSession={voice.setActiveSession}
          onDeleteSession={voice.deleteSession}
          onNewSession={() => createSession()}
        />
      </div>

      {/* Main area */}
      <div className="flex flex-1 flex-col">
        <VoiceHeader
          health={health ?? null}
          isHealthLoading={healthLoading}
        />

        <VoiceCommandBar
          onCommand={voice.executeCommand}
          disabled={voice.isRecording || voice.isProcessing}
        />

        <VoiceConversation
          messages={messages}
          isProcessing={voice.isProcessing}
        />

        <VoiceControls
          isRecording={voice.isRecording}
          isProcessing={voice.isProcessing}
          isPlaying={voice.isPlaying}
          mode={voice.mode}
          wsConnected={voice.wsConnected}
          analyserNode={voice.analyserNode}
          onRecordStart={voice.startRecording}
          onRecordStop={voice.stopRecording}
          onModeChange={voice.setMode}
          onStopPlayback={voice.stopPlayback}
        />
      </div>
    </div>
  );
}
