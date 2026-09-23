export type Role = 'admin' | 'user'

export type BookingStatus = 'pending' | 'confirmed' | 'rejected' | 'canceled' | 'completed'

export type RoomTypeStatus = 'open' | 'maintenance' | 'closed'

/** 后端统一的分页返回结构 */
export interface PageResult<T> {
  total: number
  items: T[]
}

export interface MessageResult {
  message: string
}

export interface UserInfo {
  id: number
  username: string
  name: string
  phone: string
  email: string
  role: Role
  status: number
  created_at?: string | null
}

export interface LoginResult {
  token: string
  user: UserInfo
}

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  name: string
  phone: string
  email: string
  password: string
  confirm_password: string
}

export interface ProfilePayload {
  name: string
  phone: string
  email: string
}

export interface PasswordPayload {
  old_password?: string
  new_password: string
}

export interface UserPayload extends ProfilePayload {
  role: Role
  status: number
}

export interface UserCreatePayload extends UserPayload {
  username: string
  password: string
}

export interface Hotel {
  id: number
  name: string
  city: string
  address: string
  star: number
  room_count: number
  check_in_time: string
  check_out_time: string
  status: number
  description: string
  created_at?: string | null
  room_type_count: number
  booking_count: number
}

export interface HotelPayload {
  name: string
  city: string
  address: string
  star: number
  room_count: number
  check_in_time: string
  check_out_time: string
  status: number
  description: string
}

export interface RoomType {
  id: number
  name: string
  code: string
  bed_type: string
  hotel_id: number
  hotel_name: string
  price: number
  capacity: number
  quantity: number
  status: RoomTypeStatus
  description: string
  created_at?: string | null
}

export interface RoomTypePayload {
  name: string
  code: string
  bed_type: string
  hotel_id: number
  price: number
  capacity: number
  quantity: number
  status: RoomTypeStatus
  description: string
}

/** 房态查询返回的单个房型（带实时剩余房量） */
export interface AvailabilityRoomType {
  id: number
  name: string
  bed_type: string
  price: number
  capacity: number
  quantity: number
  remaining: number
  status: RoomTypeStatus
  status_text: string
  bookable: boolean
}

export interface Availability {
  hotel_id: number
  hotel_name: string
  check_in: string
  check_out: string
  nights: number
  check_in_time: string
  check_out_time: string
  room_types: AvailabilityRoomType[]
}

export interface Booking {
  id: number
  hotel_id: number
  hotel_name: string
  room_type_id: number
  room_type_name: string
  user_id: number
  username: string
  user_name: string
  check_in_date: string
  check_out_date: string
  nights: number
  rooms: number
  guests: number
  contact_phone: string
  total_amount: number
  special_request: string
  status: BookingStatus
  status_text: string
  remark: string
  reviewer_name: string
  reviewed_at?: string | null
  created_at?: string | null
}

export interface BookingPayload {
  hotel_id: number
  room_type_id: number
  check_in_date: string
  check_out_date: string
  rooms: number
  guests: number
  contact_phone?: string
  special_request?: string
}

export interface BookingReviewPayload {
  action: 'confirm' | 'reject'
  remark: string
}

export interface HotelRankingItem {
  hotel_id: number
  hotel_name: string
  booking_count: number
}

export interface StatOverview {
  hotel_total: number
  room_type_total: number
  user_total: number
  booking_total: number
  pending_total: number
  today_check_in_total: number
  occupancy_rate: number
  week_total: number
  week_start: string
  week_end: string
  hotel_ranking: HotelRankingItem[]
  recent_bookings: Booking[]
}

export interface Knowledge {
  id: number
  category: string
  question: string
  answer: string
  keywords: string
  status: number
  created_at?: string | null
  updated_at?: string | null
}

export interface KnowledgePayload {
  category: string
  question: string
  answer: string
  keywords: string
  status: number
}

export interface AgentStatus {
  provider: string
  model: string
  llm_enabled: boolean
  knowledge_total: number
  tools: string[]
}

export interface FaqItem {
  category: string
  question: string
}

export interface ChatSession {
  id: number
  title: string
  created_at?: string | null
  updated_at?: string | null
}

/** 助手生成的订单草稿内容，字段可以缺失（信息不完整时后端会给出 problems） */
export interface BookingDraftPayload {
  hotel_id?: number | null
  hotel_name?: string
  room_type_id?: number | null
  room_type_name?: string
  check_in_date?: string
  check_out_date?: string
  nights?: number
  rooms?: number
  guests?: number
  total_amount?: number
  special_request?: string
}

export type ChatActionStatus = 'pending' | 'confirmed' | 'canceled' | 'failed'

export interface ChatAction {
  type?: string
  status?: ChatActionStatus
  payload?: BookingDraftPayload
  problems?: string[]
  note?: string
  error?: string
  booking_id?: number
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  source: string
  tools: string
  action: ChatAction | null
  created_at?: string | null
}

export interface ChatReply {
  session_id: number
  reply: ChatMessage
  suggestions: string[]
  provider: string
  action: ChatAction | null
}

export interface ChatActionResult {
  action: ChatAction
  message: ChatMessage
  booking: Booking | null
}

export interface ChatPayload {
  message: string
  session_id?: number | null
}

export interface ChatActionPayload {
  session_id: number
  message_id: number
}
