// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { cleanup,fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach,beforeEach, expect, it, vi } from 'vitest';
import { api, ApiError } from '../api';
import ContentManager from './ContentManager';

vi.mock('../api', async () => {
 const original = await vi.importActual('../api');
 return {...original, api: vi.fn()};
});
const user = {id:'editor',name:'Editor',email:'editor@example.test',role:'Content Editor',must_change_password:false};
const draft = {kind:'program',slug:'community-learning',title:'Community learning',title_ur:'اجتماعی تعلیم',description:'A local programme.',description_ur:'مقامی پروگرام۔',audience:'Residents',audience_ur:'باشندے'};
const row = {id:'doc-1',kind:'program',version:2,draft,published:{...draft,title:'Published title'},is_published:true,has_unpublished_changes:true,is_demo:true,updated_at:'2026-11-02T10:00:00Z'};
afterEach(()=>cleanup());
beforeEach(() => {
 vi.mocked(api).mockReset();
 vi.mocked(api).mockImplementation(async path => path === '/api/content/branches' ? [] : path.includes('/history') ? {items:[],total:0,offset:0,limit:10} : path.includes('/doc-1') ? row : {items:[row],total:1,offset:0,limit:25});
});
it('opens drafts with a clear published copy and authorizes server previews', async () => {
 render(<ContentManager user={user}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Edit Community learning'}));
 expect(await screen.findByLabelText('Title (English)')).toHaveValue('Community learning');
 expect(screen.getByText('Published title')).toBeInTheDocument();
 expect(screen.getByText(/Example content/)).toBeInTheDocument();
 vi.mocked(api).mockResolvedValueOnce({content:draft,version:2});
 fireEvent.click(screen.getByRole('button',{name:'Preview saved draft'}));
 await waitFor(() => expect(api).toHaveBeenCalledWith('/api/content/doc-1/preview'));
 expect(await screen.findByRole('heading',{name:'Draft preview'})).toBeInTheDocument();
});
it('preserves draft fields and shows reload action on409', async () => {
 render(<ContentManager user={user}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Edit Community learning'}));
 fireEvent.change(await screen.findByLabelText('Title (English)'),{target:{value:'My unsaved title'}});
 fireEvent.change(screen.getByLabelText('Reason for change'),{target:{value:'Correct local wording'}});
 vi.mocked(api).mockRejectedValueOnce(new ApiError(409,'Content changed. Reload before trying again.'));
 fireEvent.click(screen.getByRole('button',{name:'Save draft'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Content changed');
 expect(screen.getByLabelText('Title (English)')).toHaveValue('My unsaved title');
 expect(screen.getByRole('button',{name:'Reload latest version'})).toBeInTheDocument();
});
it('denies other staff roles without loading drafts', () => {
 render(<ContentManager user={{...user,role:'HR Lead'}}/>);
 expect(screen.getByRole('alert')).toHaveTextContent('Content Editor or Super Admin');
 expect(api).not.toHaveBeenCalled();
});
it('keeps a duplicate slug editable so the author can correct and retry',async()=>{
 render(<ContentManager user={user}/>);
 fireEvent.click(await screen.findByRole('button',{name:'New content'}));
 fireEvent.change(screen.getByLabelText('Title (English)'),{target:{value:'New program'}});
 fireEvent.change(screen.getByLabelText('Reason for change'),{target:{value:'New draft'}});
 vi.mocked(api).mockRejectedValueOnce(new ApiError(409,'This slug or page is already in use. Choose a unique value.'));
 fireEvent.submit(screen.getByRole('button',{name:'Save draft'}).closest('form')!);
 expect(await screen.findByRole('alert')).toHaveTextContent('slug or page');
 expect(screen.getByLabelText('Title (English)')).toHaveValue('New program');
 expect(screen.getByRole('button',{name:'Save draft'})).toBeEnabled();
 expect(screen.queryByRole('button',{name:'Reload latest version'})).not.toBeInTheDocument();
});
it('requires saving local edits before either publication command',async()=>{
 render(<ContentManager user={user}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Edit Community learning'}));
 fireEvent.change(await screen.findByLabelText('Title (English)'),{target:{value:'Unsaved copy'}});
 expect(screen.getByRole('button',{name:'Publish saved draft'})).toBeDisabled();
 expect(screen.getByRole('button',{name:'Unpublish'})).toBeDisabled();
});
