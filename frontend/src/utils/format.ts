import type { Booking } from '@/api/types'

export function toDateString(value?: string | null): string {
  if (!value) return ''
  return String(value).slice(0, 10)
}

export function toDateTimeString(value?: string | null): string {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 16)
}

export function weekdayText(value?: string | null): string {
  const text = toDateString(value)
  if (!text) return ''
  const target = new Date(`${text}T00:00:00`)
  if (Number.isNaN(target.getTime())) return ''
  return `周${'日一二三四五六'[target.getDay()]}`
}

/** 「2026-09-25 至 2026-09-27（2 晚）」 */
export function stayRange(row?: Pick<Booking, 'check_in_date' | 'check_out_date' | 'nights'> | null): string {
  if (!row?.check_in_date) return ''
  const nights = row.nights ?? ''
  return `${toDateString(row.check_in_date)} 至 ${toDateString(row.check_out_date)}${
    nights ? `（${nights} 晚）` : ''
  }`
}

export function money(value?: number | string | null): string {
  const amount = Number(value || 0)
  return `¥${amount.toFixed(0)}`
}
