export const API=process.env.NEXT_PUBLIC_API_URL||'https://society-maintenance-api-9bun.onrender.com';
export function auth():HeadersInit {const token=typeof window==='undefined'?'':localStorage.getItem('token')||'';return token?{Authorization:`Bearer ${token}`}:{}}
export async function request(path:string, options:RequestInit={}){
  try {
    const response=await fetch(API+path,{...options,headers:{'Content-Type':'application/json',...auth(),...options.headers}});
    if(!response.ok){
      const body=await response.json().catch(()=>({detail:'Request failed'}));
      throw new Error(body.detail||'Request failed');
    }
    return response.status===204?null:response.json();
  } catch (err) {
    if (err instanceof TypeError && err.message.includes('fetch')) {
      throw new Error('Backend API is offline or unreachable. Ensure NEXT_PUBLIC_API_URL is configured in Vercel.');
    }
    throw err;
  }
}
