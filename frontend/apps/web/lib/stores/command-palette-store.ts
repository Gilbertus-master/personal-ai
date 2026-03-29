import { create } from 'zustand';

interface CommandPaletteStore {
  open: boolean;
  query: string;
  setOpen: (v: boolean) => void;
  setQuery: (q: string) => void;
}

export const useCommandPaletteStore = create<CommandPaletteStore>()((set) => ({
  open: false,
  query: '',
  setOpen: (v) => set({ open: v }),
  setQuery: (q) => set({ query: q }),
}));
