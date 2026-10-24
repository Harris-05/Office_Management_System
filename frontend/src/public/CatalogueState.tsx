import { publicCopy } from './publicCopy';
import type { Language } from './content';

export default function CatalogueState({language,error,retry}:{language:Language;error:boolean;retry:()=>void}) {
 const copy=publicCopy[language];
 return <div className="catalogue-state" role={error?'alert':'status'}><p>{error?copy.loadError:copy.loading}</p>{error && <button className="home-button" type="button" onClick={retry}>{copy.retry}</button>}</div>;
}
