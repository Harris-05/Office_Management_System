import { content } from './content';
import type { Language } from './content';
import { pageCopy } from './pageCopy';

export default function About({ language }: { language: Language }) {
  const copy = content[language];
  const page = pageCopy[language];
  return <>
    <section className="public-intro home-section" aria-labelledby="about-heading"><h1 id="about-heading" data-home-reveal>{page.aboutTitle}</h1><div data-home-reveal><p>{page.aboutIntro}</p><a className="home-text-link" href="#our-purpose">{page.readAbout}<span aria-hidden="true"> ↓</span></a></div></section>
    <section id="our-purpose" className="about-purpose home-section" aria-labelledby="purpose-heading"><h2 id="purpose-heading" data-home-reveal>{page.purposeTitle}</h2><div data-home-reveal><p>{page.purposeBody}</p><p className="about-closing">{copy.about.closing}</p></div></section>
    <section className="about-roles home-section" aria-labelledby="roles-heading"><div className="home-section-intro"><h2 id="roles-heading" data-home-reveal>{page.rolesTitle}</h2><p data-home-reveal>{copy.about.paragraphs[1]}</p></div><div className="about-role-list">{page.roles.map(role => <article key={role.title} data-home-reveal><h3>{role.title}</h3><p>{role.body}</p></article>)}</div></section>
    <section className="about-approach home-section" aria-labelledby="approach-heading"><h2 id="approach-heading" data-home-reveal>{page.approachTitle}</h2><div data-home-reveal><p>{page.approachBody}</p><p className="public-notice">{page.approachNote}</p><a className="home-text-link" href="/branches">{copy.navigation.find(item => item.id === 'branches')!.label}<span aria-hidden="true"> ↗</span></a></div></section>
    <section className="home-next home-section" aria-labelledby="about-next"><h2 id="about-next" data-home-reveal>{copy.join.title}</h2><div data-home-reveal><p>{copy.join.body}</p><a className="home-button" href="/get-involved">{copy.hero.action}<span aria-hidden="true">↗</span></a></div></section>
  </>;
}
