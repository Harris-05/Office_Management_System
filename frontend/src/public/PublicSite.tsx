import { useEffect, useRef, useState } from 'react';
import { content } from './content';
import type { Language } from './content';
import { publicPaths } from './routes';
import type { PublicPage } from './routes';
import useScrollMotion from './useScrollMotion';
import Home from './Home';
import About from './About';
import DirectoryPage from './DirectoryPage';
import ContactPage from './ContactPage';
import './home.css';
import './pages.css';
import './scenes.css';
import './directory.css';
import './home-responsive.css';

function initialLanguage(): Language {
  try { return localStorage.getItem('branch-office-language') === 'ur' ? 'ur' : 'en'; }
  catch { return 'en'; }
}

export default function PublicSite({ page }: { page: PublicPage }) {
  const [language, setLanguage] = useState<Language>(initialLanguage);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const root = useRef<HTMLDivElement>(null);
  const copy = content[language];
  const pageLabel = copy.navigation.find(item => item.id === page)!.label;
  useScrollMotion(root, `${language}:${page}`);

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = language === 'ur' ? 'rtl' : 'ltr';
    document.title = page === 'home' ? copy.title : `${pageLabel} | ${copy.brand}`;
    const description = page === 'home' ? copy.description : page === 'about' ? copy.about.paragraphs[0] : page === 'programs' ? copy.programs.intro : copy[page].body;
    document.querySelector('meta[name="description"]')?.setAttribute('content', description);
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', '#500f1c');
    try { localStorage.setItem('branch-office-language', language); } catch { /* Reading works without storage. */ }
  }, [language, page, copy, pageLabel]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setMenuOpen(false); menuButton.current?.focus(); }
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [menuOpen]);

  const links = copy.navigation.map(item => <a key={item.id} href={publicPaths[item.id as PublicPage]} aria-current={item.id === page ? 'page' : undefined} onClick={() => setMenuOpen(false)}>{item.label}</a>);
  return <div ref={root} className={`public-site public-page-${page}`} id="top">
    <div className="home-scroll-progress" aria-hidden="true" />
    <a className="home-skip" href="#main-content">{copy.skip}</a>
    <header className="home-header">
      <a className="home-wordmark" href="/" aria-label={copy.brand}><span aria-hidden="true" className="home-mark">B</span>{copy.brand}</a>
      <nav className="home-desktop-nav" aria-label={language === 'ur' ? 'مرکزی راستے' : 'Main navigation'}>{links}</nav>
      <div className="home-header-tools">
        <div className="home-languages" aria-label={language === 'ur' ? 'زبان' : 'Language'}>
          <button type="button" lang="en" aria-pressed={language === 'en'} onClick={() => setLanguage('en')}>English</button>
          <button type="button" lang="ur" aria-pressed={language === 'ur'} onClick={() => setLanguage('ur')}>اردو</button>
        </div>
        <a className="home-staff-link" href="/staff">{copy.staff}</a>
        <button ref={menuButton} className="home-menu-button" type="button" aria-label={menuOpen ? copy.closeMenu : copy.openMenu} aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen(value => !value)}><span aria-hidden="true">{menuOpen ? '×' : <><i /><i /></>}</span></button>
      </div>
      {menuOpen && <nav id="mobile-navigation" className="home-mobile-nav" aria-label={language === 'ur' ? 'موبائل راستے' : 'Mobile navigation'}>{links}<a href="/staff">{copy.staff}</a></nav>}
    </header>
    <main id="main-content" tabIndex={-1}>
      {page === 'home' ? <Home language={language} /> : page === 'about' ? <About language={language} /> : page === 'contact' || page === 'join' ? <ContactPage language={language} join={page === 'join'} /> : <DirectoryPage page={page} language={language} />}
    </main>
    <footer className="home-footer home-section">
      <div className="home-footer-main"><div><a className="home-wordmark" href="/"><span className="home-mark" aria-hidden="true">B</span>{copy.brand}</a><p>{copy.description}</p></div><div><h2>{copy.contact.explore}</h2><nav aria-label={language === 'ur' ? 'صفحے کے راستے' : 'Footer navigation'}>{links}</nav></div><div><h2>{copy.contact.staffTitle}</h2><p>{copy.contact.staffBody}</p><a className="home-text-link" href="/staff">{copy.staff}</a></div></div>
      <div className="home-footer-bottom"><span>© {new Date().getFullYear()} {copy.brand}</span><span>{copy.footer.note}</span><a href="#top">{copy.footer.top}</a></div>
    </footer>
  </div>;
}
