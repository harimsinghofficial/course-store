import { useEffect } from 'react';
import { applyTheme, setMeta } from '../lib/theme.js';

// Keeps <title>, description, robots and theme colours right when React navigates between pages.
// (The server already rendered the correct values for whichever URL was loaded first.)
export function usePage({ title, description, robots = 'index,follow', theme }) {
  useEffect(() => {
    document.title = title;
    if (description) setMeta('description', description);
    setMeta('robots', robots);
    applyTheme(theme);
  }, [title, description, robots, theme]);
}
