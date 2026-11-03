export async function api<T>(path:string, options?:RequestInit):Promise<T> {
  const response = await fetch('/api'+path,options)
  const text = await response.text()
  let data
  try { data=JSON.parse(text) } catch { throw new Error('Backend unavailable. Start the FastAPI server and verify the frontend API proxy address.') }
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail??'Request failed'))
  return data
}
export const post = (body:unknown):RequestInit => ({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
export const upload = (file:File):RequestInit => {const body=new FormData();body.append('file',file);return {method:'POST',body}}
