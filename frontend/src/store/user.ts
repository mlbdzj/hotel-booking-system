import { create } from 'zustand'

import type { BookingStatus, Role, UserInfo } from '@/api/types'

const STORAGE_KEY = 'hotel-agent-session'

interface Session {
  token: string
  user: UserInfo | null
}

interface UserState extends Session {
  setSession: (token: string, user: UserInfo) => void
  setUser: (user: UserInfo) => void
  clear: () => void
}

function persist(session: Session) {
  if (!session.token) {
    localStorage.removeItem(STORAGE_KEY)
    return
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

function restore(): Session {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return { token: '', user: null }
  try {
    const parsed = JSON.parse(raw) as Partial<Session>
    return { token: parsed.token || '', user: parsed.user || null }
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return { token: '', user: null }
  }
}

export const useUserStore = create<UserState>((set, get) => ({
  ...restore(),
  setSession(token, user) {
    persist({ token, user })
    set({ token, user })
  },
  setUser(user) {
    const { token } = get()
    persist({ token, user })
    set({ user })
  },
  clear() {
    localStorage.removeItem(STORAGE_KEY)
    set({ token: '', user: null })
  },
}))

export const ROLE_TEXT: Record<Role, string> = {
  admin: '酒店管理员',
  user: '会员用户',
}

export const BOOKING_STATUS_TEXT: Record<BookingStatus, string> = {
  pending: '待确认',
  confirmed: '已确认',
  rejected: '已拒绝',
  canceled: '已取消',
  completed: '已完成',
}

/** antd Tag 的颜色，对应原有 Element Plus 的 tag type */
export const BOOKING_STATUS_COLOR: Record<BookingStatus, string> = {
  pending: 'warning',
  confirmed: 'success',
  rejected: 'error',
  canceled: 'default',
  completed: 'processing',
}

export const ROOM_TYPE_STATUS_TEXT = {
  open: '可预订',
  maintenance: '维护中',
  closed: '停售',
} as const

export const ROOM_TYPE_STATUS_COLOR = {
  open: 'success',
  maintenance: 'warning',
  closed: 'default',
} as const
