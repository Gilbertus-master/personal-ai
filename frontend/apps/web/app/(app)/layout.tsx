'use client';

import { useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Sidebar, Topbar, CommandPalette, UserMenu, OfflineBanner, VoiceFab, VoiceQuickPanel, ContextChatWidget } from '@gilbertus/ui';
import type { ChatContext } from '@gilbertus/ui';
import { useRole } from '@gilbertus/rbac';
import { OfflineProvider } from '@/lib/providers/offline-provider';
import { useSidebarStore } from '@/lib/stores/sidebar-store';
import { useCommandPaletteStore } from '@/lib/stores/command-palette-store';
import { useDashboardStore } from '@/lib/stores/dashboard-store';
import { useAlertsBell } from '@/lib/hooks/use-dashboard';
import { useVoice } from '@/lib/hooks/use-voice';
import UpdateBanner from '@/components/update-banner';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { collapsed, toggle } = useSidebarStore();
  const { open: commandOpen, setOpen: setCommandOpen } = useCommandPaletteStore();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [voicePanelOpen, setVoicePanelOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const { roleLevel } = useRole();
  const voice = useVoice();

  const alertsBell = useAlertsBell();
  const { dismissedAlertIds, dismissAlert } = useDashboardStore();

  // Derive chat context from current route
  const chatContext: ChatContext = (() => {
    if (!pathname) return 'general';
    if (pathname.startsWith('/brief')) return 'brief';
    if (pathname.startsWith('/compliance')) return 'compliance';
    if (pathname.startsWith('/market')) return 'market';
    if (pathname.startsWith('/finance')) return 'finance';
    if (pathname.startsWith('/intelligence')) return 'intelligence';
    if (pathname.startsWith('/people')) return 'people';
    if (pathname.startsWith('/process')) return 'process';
    if (pathname.startsWith('/decisions')) return 'decisions';
    if (pathname.startsWith('/calendar')) return 'calendar';
    if (pathname.startsWith('/documents')) return 'documents';
    if (pathname.startsWith('/voice')) return 'voice';
    if (pathname.startsWith('/admin')) return 'admin';
    return 'general';
  })();

  return (
    <OfflineProvider>
      <UpdateBanner />
      <div className="flex h-screen overflow-hidden">
        {/* Sidebar — hidden on mobile unless mobileOpen */}
        <div className="hidden md:block">
          <Sidebar collapsed={collapsed} onToggle={toggle} />
        </div>

        {/* Mobile sidebar overlay */}
        {mobileOpen && (
          <Sidebar
            collapsed={false}
            onToggle={toggle}
            mobileOpen
            onMobileClose={() => setMobileOpen(false)}
          />
        )}

        {/* Main content */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <Topbar
            onMobileMenuOpen={() => setMobileOpen(true)}
            onCommandPaletteOpen={() => setCommandOpen(true)}
            notificationAlerts={alertsBell.data?.alerts}
            notificationDismissedIds={dismissedAlertIds}
            onNotificationDismiss={dismissAlert}
            onNotificationViewAll={() => router.push('/dashboard')}
          />
          <OfflineBanner />
          <main className="flex-1 overflow-y-auto p-6">{children}</main>
        </div>

        {/* Command Palette (global overlay) */}
        <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />

        {/* Voice FAB — only for board+ roles, not on /voice page */}
        {roleLevel >= 50 && pathname !== '/voice' && (
          <>
            <VoiceFab
              roleLevel={roleLevel}
              isRecording={voice.isRecording}
              isProcessing={voice.isProcessing}
              onClick={() => setVoicePanelOpen(!voicePanelOpen)}
            />
            <VoiceQuickPanel
              isOpen={voicePanelOpen}
              onClose={() => setVoicePanelOpen(false)}
              isRecording={voice.isRecording}
              isProcessing={voice.isProcessing}
              isPlaying={voice.isPlaying}
              transcript={voice.sessions.find(s => s.id === voice.activeSessionId)?.messages.filter(m => m.role === 'user').slice(-1)[0]?.text ?? null}
              response={voice.sessions.find(s => s.id === voice.activeSessionId)?.messages.filter(m => m.role === 'assistant').slice(-1)[0]?.text ?? null}
              onRecordStart={voice.startRecording}
              onRecordStop={voice.stopRecording}
              onStopPlayback={voice.stopPlayback}
              onOpenFullPage={() => { setVoicePanelOpen(false); router.push('/voice'); }}
            />
          </>
        )}

        {/* Context-aware chat widget — hidden on /chat (has its own chat UI) */}
        {!pathname?.startsWith('/chat') && (
          <ContextChatWidget context={chatContext} />
        )}
      </div>
    </OfflineProvider>
  );
}
