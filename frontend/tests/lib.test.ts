import { describe,it,expect } from 'vitest'
import { euro,safeExternal,statuses,hour } from '../src/lib'
describe('presentazione italiana e collegamenti',()=>{
 it('mostra importi in centesimi senza float nel dominio',()=>{expect(euro(18178)).toMatch(/181,78/);expect(euro(3278)).toMatch(/32,78/)})
 it('rifiuta URL eseguibili e schemi estranei',()=>{expect(safeExternal('javascript:alert(1)')).toBe(false);expect(safeExternal('//example.test')).toBe(false);expect(safeExternal('https://example.test/menu')).toBe(true);expect(safeExternal('/menu-demo')).toBe(true)})
 it('non presenta pending come conferma e visualizza Europe/Rome',()=>{expect(statuses.PENDING_APPROVAL).toBe('Da approvare');expect(statuses.CONFIRMED).toBe('Confermata');expect(hour('2026-10-11T17:00:00Z')).toBe('19:00')})
})
