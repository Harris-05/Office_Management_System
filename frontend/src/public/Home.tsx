import { content } from './content';
import type { Language } from './content';
import { pageCopy } from './pageCopy';
import ProgramStory from './ProgramStory';
import NetworkGlobe from './NetworkGlobe';
import HomeEvents from './HomeEvents';

export default function Home({ language }: { language: Language }) {
  const copy = content[language];
  const page = pageCopy[language];
  return <>
    <section className="home-hero" aria-labelledby="home-title">
      <div className="home-hero-sheet">
        <div className="home-hero-copy">
          <h1 id="home-title" data-home-reveal>{copy.hero.title}</h1>
          <p data-home-reveal>{copy.hero.body}</p>
          <div className="home-hero-actions" data-home-reveal><a className="home-button" href="/get-involved">{copy.hero.action}<span aria-hidden="true">↗</span></a><a className="home-text-link" href="/about">{copy.hero.secondary}</a></div>
        </div>
        <NetworkGlobe language={language} />
      </div>
    </section>
    <section className="home-about home-section" aria-labelledby="about-title">
      <h2 id="about-title" data-home-reveal>{copy.about.title}</h2>
      <div className="home-letter" data-home-reveal>{copy.about.paragraphs.map(paragraph => <p key={paragraph}>{paragraph}</p>)}<a className="home-text-link" href="/about">{page.readAbout}<span aria-hidden="true"> ↗</span></a></div>
    </section>
    <ProgramStory language={language} />
    <HomeEvents language={language} />
    <section className="home-next home-closing home-section" aria-labelledby="next-title">
      <h2 id="next-title" data-home-reveal>{page.nextTitle}</h2>
      <div className="home-closing-copy" data-home-reveal><p>{page.nextBody}</p><div className="home-closing-actions"><a className="home-button" href="/branches">{copy.navigation.find(item => item.id === 'branches')!.label}<span aria-hidden="true">↗</span></a><a className="home-text-link" href="/get-involved">{copy.hero.action}<span aria-hidden="true"> ↗</span></a></div></div>
    </section>
  </>;
}
