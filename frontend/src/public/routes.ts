export const publicPaths = {
  home: '/', about: '/about', programs: '/programs', branches: '/branches',
  events: '/events', join: '/get-involved', contact: '/contact',
} as const;
export type PublicPage = keyof typeof publicPaths;

export function publicPageForPath(path: string): PublicPage | undefined {
  const normalized = path.replace(/\/$/, '') || '/';
  return (Object.keys(publicPaths) as PublicPage[]).find(page => publicPaths[page] === normalized);
}
