import { http } from '@/api/request'
import type {
  AgentStatus,
  Availability,
  Booking,
  BookingPayload,
  BookingReviewPayload,
  ChatActionPayload,
  ChatActionResult,
  ChatMessage,
  ChatPayload,
  ChatReply,
  ChatSession,
  FaqItem,
  Hotel,
  HotelPayload,
  Knowledge,
  KnowledgePayload,
  LoginPayload,
  LoginResult,
  MessageResult,
  PageResult,
  PasswordPayload,
  ProfilePayload,
  RoomType,
  RoomTypePayload,
  StatOverview,
  UserCreatePayload,
  UserInfo,
  UserPayload,
  RegisterPayload,
} from '@/api/types'

export const authApi = {
  login: (data: LoginPayload) => http.post<LoginResult>('/auth/login', data, { silent: true }),
  register: (data: RegisterPayload) => http.post<UserInfo>('/auth/register', data, { silent: true }),
  me: () => http.get<UserInfo>('/auth/me'),
  updateProfile: (data: ProfilePayload) => http.put<UserInfo>('/auth/me', data),
  changePassword: (data: PasswordPayload) => http.put<MessageResult>('/auth/password', data),
}

export const hotelApi = {
  list: (params?: Record<string, unknown>) => http.get<PageResult<Hotel>>('/hotels', params),
  detail: (id: number) => http.get<Hotel>(`/hotels/${id}`),
  availability: (id: number, checkIn: string, checkOut: string) =>
    http.get<Availability>(`/hotels/${id}/availability`, { check_in: checkIn, check_out: checkOut }),
  create: (data: HotelPayload) => http.post<Hotel>('/hotels', data),
  update: (id: number, data: HotelPayload) => http.put<Hotel>(`/hotels/${id}`, data),
  remove: (id: number) => http.delete<MessageResult>(`/hotels/${id}`),
}

export const roomTypeApi = {
  page: (params?: Record<string, unknown>) => http.get<PageResult<RoomType>>('/room-types', params),
  all: (params?: Record<string, unknown>) => http.get<RoomType[]>('/room-types/all', params),
  create: (data: RoomTypePayload) => http.post<RoomType>('/room-types', data),
  update: (id: number, data: RoomTypePayload) => http.put<RoomType>(`/room-types/${id}`, data),
  remove: (id: number) => http.delete<MessageResult>(`/room-types/${id}`),
}

export const userApi = {
  page: (params?: Record<string, unknown>) => http.get<PageResult<UserInfo>>('/users', params),
  create: (data: UserCreatePayload) => http.post<UserInfo>('/users', data),
  update: (id: number, data: UserPayload) => http.put<UserInfo>(`/users/${id}`, data),
  resetPassword: (id: number, data: { new_password: string }) =>
    http.put<MessageResult>(`/users/${id}/password`, data),
  remove: (id: number) => http.delete<MessageResult>(`/users/${id}`),
}

export const bookingApi = {
  my: (params?: Record<string, unknown>) => http.get<PageResult<Booking>>('/bookings/my', params),
  page: (params?: Record<string, unknown>) => http.get<PageResult<Booking>>('/bookings', params),
  create: (data: BookingPayload) => http.post<Booking>('/bookings', data),
  review: (id: number, data: BookingReviewPayload) => http.post<Booking>(`/bookings/${id}/review`, data),
  cancel: (id: number) => http.post<Booking>(`/bookings/${id}/cancel`),
  remove: (id: number) => http.delete<MessageResult>(`/bookings/${id}`),
}

export const statsApi = {
  overview: () => http.get<StatOverview>('/stats/overview'),
}

export const agentApi = {
  status: () => http.get<AgentStatus>('/agent/status'),
  faq: () => http.get<FaqItem[]>('/agent/faq'),
  sessions: () => http.get<ChatSession[]>('/agent/sessions'),
  createSession: () => http.post<ChatSession>('/agent/sessions'),
  messages: (sessionId: number) => http.get<ChatMessage[]>(`/agent/sessions/${sessionId}/messages`),
  removeSession: (sessionId: number) => http.delete<MessageResult>(`/agent/sessions/${sessionId}`),
  chat: (data: ChatPayload) => http.post<ChatReply>('/agent/chat', data, { silent: true }),
  confirmAction: (data: ChatActionPayload) =>
    http.post<ChatActionResult>('/agent/actions/confirm', data, { silent: true }),
  cancelAction: (data: ChatActionPayload) =>
    http.post<ChatActionResult>('/agent/actions/cancel', data, { silent: true }),
}

export const knowledgeApi = {
  page: (params?: Record<string, unknown>) => http.get<PageResult<Knowledge>>('/knowledge', params),
  categories: () => http.get<string[]>('/knowledge/categories'),
  create: (data: KnowledgePayload) => http.post<Knowledge>('/knowledge', data),
  update: (id: number, data: KnowledgePayload) => http.put<Knowledge>(`/knowledge/${id}`, data),
  remove: (id: number) => http.delete<MessageResult>(`/knowledge/${id}`),
}
