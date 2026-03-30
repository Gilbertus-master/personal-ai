// Tauri plugin type declarations
// Note: updater plugin disabled for v0.1

declare module '@tauri-apps/plugin-process' {
  export function relaunch(): Promise<void>;
}
