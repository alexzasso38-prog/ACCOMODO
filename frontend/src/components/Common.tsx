import { ReactNode, useEffect, useRef } from 'react'
import { Check, X, UtensilsCrossed, ArrowUpRight } from 'lucide-react'
import { Booking, statuses, Money, euro } from '../lib'
export function Brand(){return <a className="brand" href="/"><span className="brand-icon"><UtensilsCrossed size={22}/></span>Accomodo<span className="brand-dot">.</span></a>}
export function Badge({r}:{r:Booking}){return <span className={'badge '+r.status.toLowerCase()}><span className="status-dot"/>{statuses[r.status]||r.status}</span>}
export function ErrorBox({error}:{error:string}){return error?<div className="error" role="alert">{error}</div>:null}
export function DemoBanner(){return <div className="demo-banner"><span className="demo-dot"/>AMBIENTE DEMO · Ristoranti e ospiti fittizi. Messaggi e pagamenti sono simulati.</div>}
export function MoneySummary({value,label='Totale acconto'}:{value:Money;label?:string}){return <div className="money"><div><span>Imponibile</span><b>{euro(value.amount_net)}</b></div><div><span>IVA {value.tax_rate}%</span><b>{euro(value.tax_amount)}</b></div><div className="money-total"><span>{label}</span><b>{euro(value.amount_total)}</b></div></div>}
export function Modal({title,children,onClose}:{title:string;children:ReactNode;onClose:()=>void}){
 const ref=useRef<HTMLDialogElement>(null)
 useEffect(()=>{const last=document.activeElement as HTMLElement;ref.current?.showModal();return()=>last?.focus()},[])
 return <dialog ref={ref} onCancel={e=>{e.preventDefault();onClose()}} onClick={e=>{if(e.target===e.currentTarget)onClose()}}><div className="modal-head"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Chiudi finestra"><X/></button></div>{children}</dialog>
}
export function Empty({title,children}:{title:string;children?:ReactNode}){return <div className="empty"><span className="empty-icon"><Check size={25}/></span><h3>{title}</h3>{children}</div>}
export function External({url,children}:{url:string;children:ReactNode}){return <a className="text-link" href={url} target="_blank" rel="noreferrer">{children}<ArrowUpRight size={16}/></a>}
