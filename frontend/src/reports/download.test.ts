// @vitest-environment jsdom
import {afterEach,expect,test,vi} from 'vitest';
import {downloadReport} from './download';

afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals();vi.useRealTimers();});

test('saves the complete PDF blob and releases its object URL',async()=>{
 vi.useFakeTimers();
 const fetcher=vi.fn().mockResolvedValue(new Response('%PDF-synthetic',{headers:{'Content-Type':'application/pdf'}}));
 vi.stubGlobal('fetch',fetcher);
 const create=vi.fn().mockReturnValue('blob:report-pdf');const revoke=vi.fn();
 Object.defineProperty(URL,'createObjectURL',{configurable:true,value:create});
 Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:revoke});
 let clicked:HTMLAnchorElement|null=null;
 vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(function(this:HTMLAnchorElement){clicked=this;});
 await downloadReport('report','pdf','RPT-BR-000001-2026-10-26');
 expect(fetcher).toHaveBeenCalledWith('/api/reports/report/export.pdf',expect.objectContaining({credentials:'same-origin'}));
 expect(clicked!.download).toBe('RPT-BR-000001-2026-10-26.pdf');
 expect(clicked!.href).toBe('blob:report-pdf');expect(create.mock.calls[0][0]).toBeInstanceOf(Blob);
 expect(document.querySelector('a')).toBeNull();
 vi.advanceTimersByTime(1000);expect(revoke).toHaveBeenCalledWith('blob:report-pdf');
});
