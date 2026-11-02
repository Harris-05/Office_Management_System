import {useEffect,useState} from 'react';
import {api} from '../api';

export default function useResource<T>(path:string) {
 const [data,setData]=useState<T|null>(null);
 const [error,setError]=useState('');
 const [loading,setLoading]=useState(true);
 const [attempt,setAttempt]=useState(0);
 useEffect(()=>{
  let current=true;
  setData(null);setError('');setLoading(true);
  api<T>(path).then(value=>{if(current)setData(value);}).catch(cause=>{if(current)setError(cause instanceof Error?cause.message:'Unable to load this information.');}).finally(()=>{if(current)setLoading(false);});
  return()=>{current=false;};
 },[path,attempt]);
 return {data,error,loading,reload:()=>setAttempt(value=>value+1)};
}
