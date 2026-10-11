export type Booking = {id:string; public_reference:string; starts_at:string; ends_at:string; party_size:number;status:string;version:number;name:string;source:string;tables?:string[];deposit?:Money;expires_at?:string}
export type Money = {amount_net:number; tax_amount:number;amount_total:number;tax_rate:string;currency:string}
export type Venue = {name:string;slug:string;address:string;timezone:string;booking_mode:string;max_party_size:number;menu_url:string;directions_url:string;pending_policy:string;deposit:Money;demo:boolean}
export type Slot = {starts_at:string;ends_at:string;label:string}
export const statuses:Record<string,string>={HOLD:'Opzione temporanea',PENDING_APPROVAL:'Da approvare',AWAITING_PAYMENT:'In attesa di acconto',CONFIRMED:'Confermata',SEATED:'Al tavolo',COMPLETED:'Completata',CANCELLED:'Cancellata',EXPIRED:'Scaduta',REJECTED:'Non accettata',NO_SHOW:'Non presentato'}
export const euro=(cents:number)=>new Intl.NumberFormat('it-IT',{style:'currency',currency:'EUR'}).format(cents/100)
export const localDay=(offset=0)=>{const d=new Date();d.setDate(d.getDate()+offset);return new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome'}).format(d)}
export const hour=(d:string)=>new Intl.DateTimeFormat('it-IT',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(new Date(d))
export const niceDay=(d:string)=>new Intl.DateTimeFormat('it-IT',{weekday:'long',day:'numeric',month:'long',timeZone:'Europe/Rome'}).format(new Date(d+'T12:00:00'))
export async function api<T>(path:string,method='GET',body?:unknown,token?:string):Promise<T>{
 const headers:Record<string,string>={'Content-Type':'application/json'}
 const csrf=sessionStorage.getItem('csrf'); if(csrf) headers['X-CSRF-Token']=csrf
 if(token) headers['X-Booking-Token']=token
 const res=await fetch('/api'+path,{method,headers,credentials:'include',body:body===undefined?undefined:JSON.stringify(body)})
 if(!res.ok){const data=await res.json().catch(()=>({detail:'Servizio temporaneamente non disponibile.'}));throw new Error(typeof data.detail==='string'?data.detail:'Controlla i dati inseriti, compresi recapito e fuso orario.')}
 return res.json()
}
export function safeExternal(url:string|undefined){return !!url && (url.startsWith('/')&&!url.startsWith('//')||/^https:\/\//.test(url))}

export const dayOf=(d:string)=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome'}).format(new Date(d))
