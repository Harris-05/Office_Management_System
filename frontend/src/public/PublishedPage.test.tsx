import {cleanup,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import About from './About';
import Home from './Home';
import ContactPage from './ContactPage';

vi.mock('./ProgramStory',()=>({default:()=>null}));
vi.mock('./HomeEvents',()=>({default:()=>null}));
vi.mock('./NetworkGlobe',()=>({default:()=>null}));
vi.mock('./PublicForm',()=>({default:()=>null}));
const page={id:'about',slug:'about-us',page_key:'about',is_demo:false,title:'Our local work',title_ur:'ہمارا مقامی کام',description:'<script>untrusted()</script>\nA second line.',description_ur:'ہماری مقامی کوشش۔'};
beforeEach(()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({branches:[],programs:[],events:[],pages:[page]})}));});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('uses published bilingual page introductions as escaped plain text',async()=>{
 const {rerender}=render(<About language="en"/>);
 expect(await screen.findByRole('heading',{name:'Our local work',level:1})).toBeInTheDocument();
 expect(screen.getByText(/<script>untrusted/)).toBeInTheDocument();
 expect(document.querySelector('script')).toBeNull();
 rerender(<About language="ur"/>);
 expect(await screen.findByRole('heading',{name:'ہمارا مقامی کام',level:1})).toBeInTheDocument();
 expect(screen.getByText('ہماری مقامی کوشش۔')).toBeInTheDocument();
});
it('keeps original copy when there is no published introduction',async()=>{
 render(<Home language="en"/>);
 expect(screen.getByRole('heading',{level:1})).toHaveTextContent(/\S/);
 expect(screen.queryByRole('heading',{name:'Our local work'})).not.toBeInTheDocument();
});
it('uses contact publication without changing get-involved content',async()=>{
 vi.mocked(fetch).mockResolvedValue({ok:true,json:async()=>({branches:[],programs:[],events:[],pages:[{...page,page_key:'contact',title:'Contact our office'}]})} as Response);
 const {rerender}=render(<ContactPage language="en"/>);
 expect(await screen.findByRole('heading',{name:'Contact our office',level:1})).toBeInTheDocument();
 rerender(<ContactPage language="en" join/>);
 expect(screen.queryByRole('heading',{name:'Contact our office',level:1})).not.toBeInTheDocument();
});
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
