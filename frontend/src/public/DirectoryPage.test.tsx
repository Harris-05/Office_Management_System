// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import DirectoryPage from './DirectoryPage';

afterEach(() => {cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); history.replaceState(null,'','/');});
const branch = (name: string, city: string) => ({id:city,slug:city,name,name_ur:name,city,city_ur:city,description:'Local community team',description_ur:'تفصیل',address:'Demo location',address_ur:'مثالی مقام',hours:'Weekdays',hours_ur:'اوقات',is_demo:true});
test('loads real catalogue results and filters branch names and cities', async () => {
 vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok:true,json:async()=>({branches:[branch('Karachi branch','Karachi'),branch('Lahore branch','Lahore')],programs:[],events:[]})}));
 render(<DirectoryPage page="branches" language="en" />);
 expect(await screen.findByRole('heading',{name:'Karachi branch'})).toBeInTheDocument();
 await userEvent.type(screen.getByLabelText('Search branches'),'Lahore');
 expect(screen.queryByRole('heading',{name:'Karachi branch'})).not.toBeInTheDocument();
 expect(screen.getByRole('heading',{name:'Lahore branch'})).toBeVisible();
});
test('network failure offers retry instead of claiming there are no records', async () => {
 vi.stubGlobal('fetch',vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ok:true,json:async()=>({branches:[],programs:[],events:[]})}));
 render(<DirectoryPage page="events" language="en" />);
 expect(await screen.findByRole('alert')).toHaveTextContent('couldn’t load');
 await userEvent.click(screen.getByRole('button',{name:'Try again'}));
 expect(await screen.findByText('No matches yet')).toBeInTheDocument();
});

test('an event deep link reaches its article after asynchronous content loads', async () => {
 history.replaceState(null,'','/events#sample-event');
 const scroll=vi.fn();
 HTMLElement.prototype.scrollIntoView=scroll;
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({branches:[],programs:[],events:[{id:'1',slug:'sample-event',is_demo:true,title:'A sample event',title_ur:'نمونہ تقریب',description:'Event information',description_ur:'تفصیل',branch_id:'1',starts_at:'2099-10-01T10:00:00Z',ends_at:'2099-10-01T12:00:00Z'}]})}));
 render(<DirectoryPage page="events" language="en"/>);
 expect(await screen.findByRole('heading',{name:'A sample event'})).toBeInTheDocument();
 expect(scroll).toHaveBeenCalled();
 expect(scroll.mock.instances[0]).toHaveAttribute('id','sample-event');
});
