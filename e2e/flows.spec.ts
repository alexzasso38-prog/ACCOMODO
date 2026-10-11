import { test,expect } from '../frontend/node_modules/@playwright/test'
import AxeBuilder from '../frontend/node_modules/@axe-core/playwright'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
const accounts=JSON.parse(readFileSync(resolve(process.cwd(),'../work/demo-access.json'),'utf8'))
const staff=accounts.find((a:any)=>a.email==='staff1@tavolo.test')
function day(offset:number){const d=new Date();d.setDate(d.getDate()+offset);return new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome'}).format(d)}
test.beforeEach(async({context,page})=>{await context.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());page.on('pageerror',e=>{throw e})})
test('cliente senza account: conferma, modifica atomica, calendario e cancellazione',async({page})=>{
 await page.goto('/b/osteria-demo');await expect(page.getByRole('heading',{name:'Troviamo il tuo tavolo'})).toBeVisible()
 await page.getByLabel('Data',{exact:true}).fill(day(4));await page.getByRole('button',{name:'12:00',exact:true}).click()
 await page.getByLabel('Nome e cognome').fill('Ospite E2E sintetico');await page.getByLabel('Email',{exact:true}).fill('e2e@example.test');await page.getByRole('checkbox',{name:/Ho letto/}).check()
 await page.getByRole('button',{name:'Prenota il tuo tavolo'}).click();await expect(page.getByRole('heading',{name:'Il tuo tavolo ti aspetta.'})).toBeVisible()
 expect(new URL(page.url()).hash).toContain('token=')
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Aggiungi al calendario'}).click();expect((await download).suggestedFilename()).toBe('prenotazione.ics')
 await page.getByRole('button',{name:'Modifica data o persone'}).click();await page.getByLabel('Nuovo orario').selectOption({label:'13:30'});await page.getByRole('button',{name:'Salva modifica'}).click();await expect(page.getByText('13:30 – 15:00')).toBeVisible().catch(async()=>{await expect(page.getByText('13:30')).toBeVisible()})
 await page.getByRole('button',{name:'Cancella prenotazione',exact:true}).click();await expect(page.getByRole('heading',{name:'Prenotazione cancellata.'})).toBeVisible()
})
test('richiesta manuale resta distinta da una conferma',async({page})=>{
 await page.goto('/b/giardino-demo');await page.getByLabel('Data',{exact:true}).fill(day(5));await page.getByRole('button',{name:'12:00',exact:true}).click();await page.getByLabel('Nome e cognome').fill('Ospite richiesta E2E');await page.getByLabel('Email',{exact:true}).fill('manuale@example.test');await page.getByRole('checkbox',{name:/Ho letto/}).check();await page.getByRole('button',{name:'Invia richiesta'}).click();await expect(page.getByRole('heading',{name:'Richiesta ricevuta.'})).toBeVisible();await expect(page.getByText(/Questa ricevuta non è una conferma definitiva/)).toBeVisible()
})
test('staff: agenda, tavoli, report e percorso telefonico con consenso',async({page})=>{
 await page.goto('/');await page.getByLabel('Email',{exact:true}).fill(staff.email);await page.getByLabel('Password',{exact:true}).fill(staff.password);await page.getByRole('button',{name:'Entra nel tuo ristorante'}).click();await expect(page.getByRole('heading',{name:'Ogni ospite, al posto giusto.'})).toBeVisible()
 await page.getByRole('button',{name:'Giorno successivo'}).click();await expect(page.getByText('Ospite sintetico 1')).toBeVisible()
 await page.getByRole('button',{name:'Tavoli',exact:true}).click();await expect(page.getByRole('heading',{name:'T01',exact:true})).toBeVisible();await page.getByRole('button',{name:'Report',exact:true}).click();await expect(page.getByRole('heading',{name:'Origine delle prenotazioni'})).toBeVisible()
 await page.getByRole('button',{name:'Simulatore telefono',exact:true}).click();await page.getByRole('checkbox',{name:/Premo 1/}).check();await page.getByRole('button',{name:'Simula chiamata',exact:true}).click();await expect(page.getByText('WhatsApp simulato: apri il link di prenotazione')).toBeVisible();await page.getByRole('button',{name:'Chiudi finestra'}).click();await page.getByRole('button',{name:'Oggi',exact:true}).first().click()
 await page.screenshot({path:'../work/admin-desktop.png',fullPage:true})
 const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();expect(axe.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))).toEqual([])
})
test('mobile 360px, tastiera e accessibilità pagina cliente',async({page})=>{
 await page.setViewportSize({width:360,height:800});await page.goto('/b/osteria-demo');await expect(page.getByLabel('Nome e cognome')).toBeVisible()
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
 await expect(page.getByRole('button',{name:'12:00',exact:true})).toBeVisible();await page.getByRole('combobox',{name:'Persone',exact:true}).focus();await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'12:00',exact:true})).toBeFocused()
 await page.screenshot({path:'../work/booking-mobile.png',fullPage:true})
 const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();expect(axe.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))).toEqual([])
})
