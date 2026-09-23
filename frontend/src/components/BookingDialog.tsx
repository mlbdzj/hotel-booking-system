import { useCallback, useEffect, useState } from 'react'
import { DatePicker, Form, Input, InputNumber, Modal, Select, Tag } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'

import { bookingApi, hotelApi } from '@/api'
import type { Availability, AvailabilityRoomType, Hotel } from '@/api/types'
import { feedback } from '@/utils/feedback'
import { money } from '@/utils/format'

const DAY_FORMAT = 'YYYY-MM-DD'

export interface BookingDialogProps {
  open: boolean
  /** 指定酒店时锁定酒店选择（从酒店页「预订」按钮进入） */
  hotel?: Hotel | null
  hotels?: Hotel[]
  onClose: () => void
  onSuccess?: () => void
}

interface BookingFormValues {
  hotel_id: number
  date_range: [Dayjs, Dayjs]
  room_type_id: number
  rooms: number
  guests: number
  special_request?: string
}

function disabledDate(current: Dayjs): boolean {
  return current.valueOf() < Date.now() - 24 * 60 * 60 * 1000
}

const roomTypeLabel = (item: AvailabilityRoomType) =>
  `${item.name}（${item.bed_type}）${money(item.price)}/晚 · 剩余 ${item.remaining} 间`

export default function BookingDialog({ open, hotel, hotels = [], onClose, onSuccess }: BookingDialogProps) {
  const [form] = Form.useForm<BookingFormValues>()
  const [submitting, setSubmitting] = useState(false)
  const [availabilityLoading, setAvailabilityLoading] = useState(false)
  const [hotelList, setHotelList] = useState<Hotel[]>([])
  const [availability, setAvailability] = useState<Availability | null>(null)
  const [roomTypeOptions, setRoomTypeOptions] = useState<AvailabilityRoomType[]>([])

  const hotelOptions = hotels.length ? hotels : hotelList

  const hotelId = Form.useWatch('hotel_id', form)
  const dateRange = Form.useWatch('date_range', form)
  const rooms = Form.useWatch('rooms', form)
  const selectedRoomTypeId = Form.useWatch('room_type_id', form)

  const checkInText = dateRange?.[0]?.format(DAY_FORMAT) ?? ''
  const checkOutText = dateRange?.[1]?.format(DAY_FORMAT) ?? ''

  const selectedRoomType = roomTypeOptions.find((item) => item.id === selectedRoomTypeId) || null
  const nights = dateRange?.[0] && dateRange?.[1] ? Math.max(0, dateRange[1].diff(dateRange[0], 'day')) : 0
  const currentRooms = rooms || 1
  const totalAmount = (selectedRoomType?.price || 0) * nights * currentRooms
  const maxRooms = Math.max(1, Math.min(20, selectedRoomType?.remaining || 20))
  const maxGuests = Math.max(1, (selectedRoomType?.capacity || 2) * currentRooms)

  const loadAvailability = useCallback(
    async (targetHotelId: number, checkIn: string, checkOut: string) => {
      setAvailabilityLoading(true)
      try {
        const data = await hotelApi.availability(targetHotelId, checkIn, checkOut)
        setAvailability(data)
        setRoomTypeOptions(data.room_types)
      } catch {
        setAvailability(null)
        setRoomTypeOptions([])
      } finally {
        setAvailabilityLoading(false)
      }
    },
    [],
  )

  // 打开弹窗时重置表单，并准备好酒店下拉选项
  useEffect(() => {
    if (!open) return
    let cancelled = false

    const init = async () => {
      let options = hotels
      if (!options.length) {
        try {
          const data = await hotelApi.list({ page_size: 100 })
          if (cancelled) return
          setHotelList(data.items)
          options = data.items
        } catch {
          // 请求层已经提示过错误
        }
      }
      if (cancelled) return

      const checkIn = dayjs().add(1, 'day')
      form.setFieldsValue({
        hotel_id: hotel?.id ?? options[0]?.id,
        date_range: [checkIn, checkIn.add(1, 'day')],
        room_type_id: undefined as unknown as number,
        rooms: 1,
        guests: 1,
        special_request: '',
      })
      form.setFields([{ name: 'room_type_id', errors: [] }])
      setAvailability(null)
      setRoomTypeOptions([])
    }

    void init()
    return () => {
      cancelled = true
    }
    // 只在弹窗打开时初始化，hotels / hotel 变化不需要重跑
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // 酒店或日期变化时刷新房态
  useEffect(() => {
    if (!open || !hotelId || !checkInText || !checkOutText) return
    if (checkOutText <= checkInText) return
    void loadAvailability(hotelId, checkInText, checkOutText)
  }, [open, hotelId, checkInText, checkOutText, loadAvailability])

  const handleRoomTypeChange = (value: number) => {
    const target = roomTypeOptions.find((item) => item.id === value)
    if (!target) return
    const limit = Math.max(1, Math.min(20, target.remaining || 20))
    if ((form.getFieldValue('rooms') || 1) > limit) form.setFieldValue('rooms', limit)
    const guestLimit = Math.max(1, target.capacity * (form.getFieldValue('rooms') || 1))
    if ((form.getFieldValue('guests') || 1) > guestLimit) form.setFieldValue('guests', guestLimit)
  }

  const handleRoomsChange = (value: number | null) => {
    const nextRooms = value || 1
    const guestLimit = Math.max(1, (selectedRoomType?.capacity || 2) * nextRooms)
    if ((form.getFieldValue('guests') || 1) > guestLimit) form.setFieldValue('guests', guestLimit)
  }

  const submit = async () => {
    const values = await form.validateFields().catch(() => null)
    if (!values) return

    const [checkIn, checkOut] = values.date_range
    const stayNights = checkOut.diff(checkIn, 'day')
    if (stayNights <= 0) {
      feedback.warning('退房日期必须晚于入住日期')
      return
    }
    const guestLimit = Math.max(1, (selectedRoomType?.capacity || 2) * values.rooms)
    if (values.guests > guestLimit) {
      feedback.warning('入住人数超过房型可住人数上限，请增加房间数')
      return
    }

    setSubmitting(true)
    try {
      await bookingApi.create({
        hotel_id: values.hotel_id,
        room_type_id: values.room_type_id,
        check_in_date: checkIn.format(DAY_FORMAT),
        check_out_date: checkOut.format(DAY_FORMAT),
        rooms: values.rooms,
        guests: values.guests,
        special_request: values.special_request || '',
      })
      feedback.success('订单已提交，等待酒店确认')
      onSuccess?.()
      onClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title="预订酒店"
      open={open}
      width={660}
      okText="提交订单"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={submit}
      onCancel={onClose}
    >
      <Form form={form} labelCol={{ span: 5 }} wrapperCol={{ span: 19 }} style={{ marginTop: 20 }}>
        <Form.Item label="酒店" name="hotel_id" rules={[{ required: true, message: '请选择酒店' }]}>
          <Select
            placeholder="请选择酒店"
            disabled={Boolean(hotel)}
            onChange={() => form.setFieldValue('room_type_id', undefined as unknown as number)}
            options={hotelOptions.map((item) => ({
              value: item.id,
              label: `${item.name}（${item.city} ${item.address}）`,
              disabled: item.status !== 1,
            }))}
          />
        </Form.Item>

        <Form.Item
          label="入住 / 退房"
          name="date_range"
          rules={[{ required: true, message: '请选择入住与退房日期' }]}
        >
          <DatePicker.RangePicker
            style={{ width: '100%' }}
            format={DAY_FORMAT}
            disabledDate={disabledDate}
            onChange={() => form.setFieldValue('room_type_id', undefined as unknown as number)}
          />
        </Form.Item>

        <Form.Item label="房型" name="room_type_id" rules={[{ required: true, message: '请选择房型' }]}>
          <Select
            placeholder="请先选择酒店与日期"
            loading={availabilityLoading}
            onChange={handleRoomTypeChange}
            options={roomTypeOptions.map((item) => ({
              value: item.id,
              label: roomTypeLabel(item),
              disabled: !item.bookable,
            }))}
          />
        </Form.Item>

        {/* 带 name 的 Form.Item 只能有一个子元素，提示文案用 extra 承载 */}
        <Form.Item
          label="间数"
          name="rooms"
          rules={[{ required: true, message: '请输入间数' }]}
          extra={`该房型剩余 ${selectedRoomType?.remaining ?? '-'} 间`}
        >
          <InputNumber min={1} max={maxRooms} onChange={handleRoomsChange} />
        </Form.Item>

        <Form.Item
          label="入住人数"
          name="guests"
          rules={[{ required: true, message: '请输入入住人数' }]}
          extra={selectedRoomType ? `每间可住 ${selectedRoomType.capacity} 人` : '请选择房型'}
        >
          <InputNumber min={1} max={maxGuests} />
        </Form.Item>

        <Form.Item label="特殊要求">
          <Form.Item name="special_request" noStyle>
            <Input.TextArea
              rows={2}
              maxLength={200}
              showCount
              placeholder="例如：安静楼层、需要加床、晚到店"
            />
          </Form.Item>
        </Form.Item>

        <Form.Item label="费用预估">
          {nights > 0 && selectedRoomType ? (
            <div style={{ color: '#303133' }}>
              共 <b>{nights}</b> 晚 · <b>{currentRooms}</b> 间 · 总价{' '}
              <b style={{ color: '#f56c6c', fontSize: 16 }}>{money(totalAmount)}</b>
              <div style={{ marginTop: 4, color: '#909399', fontSize: 12 }}>
                入住 {availability?.check_in_time || '-'} 之后，退房 {availability?.check_out_time || '-'}{' '}
                之前，房价未含到店可能产生的押金与加床费用
              </div>
            </div>
          ) : (
            <span style={{ color: '#909399' }}>请选择酒店、日期与房型</span>
          )}
        </Form.Item>

        <Form.Item label="房态">
          {roomTypeOptions.length ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {roomTypeOptions.map((item) => (
                <Tag key={item.id} color={item.bookable ? 'success' : 'default'}>
                  {item.name}：{item.status_text}，剩余 {item.remaining} 间
                </Tag>
              ))}
            </div>
          ) : (
            <span style={{ color: '#909399' }}>选择日期后显示房型与剩余房量</span>
          )}
        </Form.Item>
      </Form>
    </Modal>
  )
}
