import {ApiError} from '../api';

/** Save an authorized blob while preserving report inputs and visible API errors. */
export async function downloadReport(id:string,format:'pdf'|'csv',code:string):Promise<void>{
  let response:Response;
  try{
    response=await fetch(`/api/reports/${encodeURIComponent(id)}/export.${format}`,{credentials:'same-origin',signal:AbortSignal.timeout(30000)});
  }catch{throw new Error('Unable to download. Check your connection and try again.');}
  if(!response.ok){
    if(response.status===401)window.dispatchEvent(new Event('branch-session-invalid'));
    const body=await response.json().catch(()=>undefined);
    throw new ApiError(response.status,typeof body?.detail==='string'?body.detail:'Unable to export report. Please try again.');
  }
  const blob=await response.blob();
  const url=URL.createObjectURL(blob);
  const anchor=document.createElement('a');
  anchor.href=url;anchor.download=`${code.replace(/[^a-zA-Z0-9_-]/g,'_')}.${format}`;
  document.body.append(anchor);anchor.click();anchor.remove();
  window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}
