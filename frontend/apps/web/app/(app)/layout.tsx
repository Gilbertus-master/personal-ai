'use client';

import { useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Sidebar, Topbar, CommandPalette, UserMenu, OfflineBanner, VoiceFab, VoiceQuickPanel } from '@gilbertus/ui';
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
      </div>
    </OfflineProvider>
  );
}
