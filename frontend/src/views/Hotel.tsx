import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Rate,
  Row,
  Select,
  Spin,
  Switch,
  Table,
  Tag,
  theme,
  TimePicker,
  type TableColumnsType,
} from 'antd'
import {
  AppstoreOutlined,
  ClockCircleOutlined,
  EnvironmentOutlined,
  PlusOutlined,
  StarOutlined,
} from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'

import { hotelApi } from '@/api'
import type { Hotel as HotelRecord, HotelPayload } from '@/api/types'
import BookingDialog from '@/components/BookingDialog'
import { useUserStore } from '@/store/user'
import { feedback } from '@/utils/feedback'

const PAGE_SIZE = 10

const STATUS_OPTIONS = [
  { label: '营业中', value: 1 },
  { label: '暂停营业', value: 0 },
]

interface HotelFormValues extends Omit<HotelPayload, 'status' | 'check_in_time' | 'check_out_time'> {
  check_in_time: string
  check_out_time: string
  status: number
}

export default function Hotel() {
  const isAdmin = useUserStore((state) => state.user?.role === 'admin')
  const { token } = theme.useToken()

  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [hotels, setHotels] = useState<HotelRecord[]>([])
  const [total, setTotal] = useState(0)
  const [keywordInput, setKeywordInput] = useState('')
  const [query, setQuery] = useState<{ keyword: string; status: number | ''; page: number }>({
    keyword: '',
    status: '',
    page: 1,
  })

  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form] = Form.useForm<HotelFormValues>()

  const [bookingOpen, setBookingOpen] = useState(false)
  const [currentHotel, setCurrentHotel] = useState<HotelRecord | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await hotelApi.list({
        keyword: query.keyword,
        status: query.status,
        page: query.page,
        page_size: PAGE_SIZE,
      })
      setHotels(data.items)
      setTotal(data.total)
    } catch {
      // 请求层已经提示过错误
    } finally {
      setLoading(false)
    }
  }, [query])

  useEffect(() => {
    void load()
  }, [load])

  const search = () => setQuery((prev) => ({ ...prev, keyword: keywordInput, page: 1 }))

  const openForm = (row?: HotelRecord) => {
    setEditingId(row?.id ?? null)
    form.setFieldsValue({
      name: row?.name || '',
      city: row?.city || '',
      address: row?.address || '',
      star: row?.star || 4,
      room_count: row?.room_count || 100,
      check_in_time: row?.check_in_time || '14:00',
      check_out_time: row?.check_out_time || '12:00',
      status: row?.status ?? 1,
      description: row?.description || '',
    })
    setFormOpen(true)
  }

  const submitForm = async () => {
    const values = await form.validateFields().catch(() => null)
    if (!values) return
    setSubmitting(true)
    try {
      const payload: HotelPayload = {
        name: values.name,
        city: values.city,
        address: values.address,
        star: values.star,
        room_count: values.room_count,
        check_in_time: values.check_in_time,
        check_out_time: values.check_out_time,
        status: values.status,
        description: values.description,
      }
      if (editingId) await hotelApi.update(editingId, payload)
      else await hotelApi.create(payload)
      feedback.success('保存成功')
      setFormOpen(false)
      await load()
    } finally {
      setSubmitting(false)
    }
  }

  const remove = (row: HotelRecord) => {
    feedback.confirm({
      title: '提示',
      content: `确定删除酒店「${row.name}」吗？`,
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await hotelApi.remove(row.id)
        feedback.success('删除成功')
        await load()
      },
    })
  }

  const openBooking = (row: HotelRecord) => {
    setCurrentHotel(row)
    setBookingOpen(true)
  }

  const columns: TableColumnsType<HotelRecord> = [
    { title: '酒店名称', dataIndex: 'name', width: 170, ellipsis: true },
    { title: '城市', dataIndex: 'city', width: 80 },
    { title: '地址', dataIndex: 'address', width: 180, ellipsis: true },
    { title: '星级', width: 80, render: (_, row) => `${row.star} 星` },
    { title: '客房数', dataIndex: 'room_count', width: 80 },
    {
      title: '入住/退房',
      width: 120,
      render: (_, row) => `${row.check_in_time} / ${row.check_out_time}`,
    },
    { title: '房型', dataIndex: 'room_type_count', width: 70 },
    { title: '订单', dataIndex: 'booking_count', width: 70 },
    {
      title: '状态',
      width: 90,
      render: (_, row) => (
        <Tag color={row.status === 1 ? 'success' : 'default'}>{row.status === 1 ? '营业中' : '暂停营业'}</Tag>
      ),
    },
    {
      title: '操作',
      width: 150,
      fixed: 'right',
      render: (_, row) => (
        <>
          <Button type="link" onClick={() => openBooking(row)}>
            预订
          </Button>
          <Button type="link" onClick={() => openForm(row)}>
            编辑
          </Button>
          <Button type="link" danger onClick={() => remove(row)}>
            删除
          </Button>
        </>
      ),
    },
  ]

  return (
    <div>
      <Card variant="borderless">
        <div className="page-block-head">
          <div className="page-title">酒店管理</div>
          <div className="page-toolbar">
            <Input.Search
              value={keywordInput}
              placeholder="搜索酒店名称/地址"
              allowClear
              style={{ width: 220 }}
              onChange={(event) => setKeywordInput(event.target.value)}
              onSearch={search}
            />
            <Select
              value={query.status === '' ? undefined : query.status}
              placeholder="营业状态"
              allowClear
              style={{ width: 140 }}
              options={STATUS_OPTIONS}
              onChange={(value) => setQuery((prev) => ({ ...prev, status: value ?? '', page: 1 }))}
            />
            {isAdmin && (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => openForm()}>
                新增酒店
              </Button>
            )}
          </div>
        </div>
      </Card>

      {isAdmin ? (
        <Card variant="borderless" style={{ marginTop: 16 }}>
          <Table<HotelRecord>
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={hotels}
            scroll={{ x: 1090 }}
            locale={{ emptyText: '暂无酒店数据' }}
            pagination={{
              current: query.page,
              pageSize: PAGE_SIZE,
              total,
              showSizeChanger: false,
              showTotal: (value) => `共 ${value} 条`,
              onChange: (page) => setQuery((prev) => ({ ...prev, page })),
            }}
          />
        </Card>
      ) : (
        <Spin spinning={loading}>
          <Row gutter={16} style={{ marginTop: 16 }}>
            {hotels.map((item) => (
              <Col key={item.id} xs={24} sm={12} lg={8}>
                <Card variant="borderless" hoverable style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 16, fontWeight: 'bold' }}>{item.name}</span>
                    <Tag color={item.status === 1 ? 'success' : 'default'}>
                      {item.status === 1 ? '营业中' : '暂停营业'}
                    </Tag>
                  </div>
                  <div style={{ marginTop: 10, color: token.colorTextSecondary, lineHeight: '24px' }}>
                    <div>
                      <EnvironmentOutlined /> {item.city} · {item.address || '地址待补充'}
                    </div>
                    <div>
                      <StarOutlined /> {item.star} 星酒店 · 客房 {item.room_count} 间
                    </div>
                    <div>
                      <ClockCircleOutlined /> 入住 {item.check_in_time} 之后 / 退房 {item.check_out_time} 之前
                    </div>
                    <div>
                      <AppstoreOutlined /> 可预订房型 {item.room_type_count} 种
                    </div>
                  </div>
                  <div style={{ marginTop: 10, color: token.colorTextTertiary, minHeight: 40 }}>
                    {item.description}
                  </div>
                  <Button
                    type="primary"
                    block
                    style={{ marginTop: 8 }}
                    disabled={item.status !== 1}
                    onClick={() => openBooking(item)}
                  >
                    立即预订
                  </Button>
                </Card>
              </Col>
            ))}
            {!hotels.length && (
              <Col span={24}>
                <Empty description="暂无可预订的酒店" />
              </Col>
            )}
          </Row>
        </Spin>
      )}

      <Modal
        title={editingId ? '编辑酒店' : '新增酒店'}
        open={formOpen}
        width={560}
        okText="保存"
        cancelText="取消"
        confirmLoading={submitting}
        onOk={submitForm}
        onCancel={() => setFormOpen(false)}
      >
        <Form form={form} labelCol={{ span: 6 }} wrapperCol={{ span: 18 }} style={{ marginTop: 20 }}>
          <Form.Item label="酒店名称" name="name" rules={[{ required: true, message: '请输入酒店名称' }]}>
            <Input placeholder="例如：杭州西湖智选假日酒店" />
          </Form.Item>
          <Form.Item label="城市" name="city" rules={[{ required: true, message: '请输入城市' }]}>
            <Input placeholder="例如：杭州" />
          </Form.Item>
          <Form.Item label="地址" name="address">
            <Input placeholder="例如：西湖区文三路 88 号" />
          </Form.Item>
          <Form.Item label="星级" name="star">
            <Rate />
          </Form.Item>
          <Form.Item label="客房数" name="room_count" rules={[{ required: true, message: '请输入客房数' }]}>
            <InputNumber min={1} max={5000} />
          </Form.Item>
          <Form.Item
            label="入住时间"
            name="check_in_time"
            rules={[{ required: true, message: '请选择入住时间' }]}
            getValueProps={(value?: string) => ({ value: value ? dayjs(value, 'HH:mm') : undefined })}
            normalize={(value?: Dayjs | null) => (value ? value.format('HH:mm') : '')}
          >
            <TimePicker format="HH:mm" minuteStep={30} style={{ width: 150 }} />
          </Form.Item>
          <Form.Item
            label="退房时间"
            name="check_out_time"
            rules={[{ required: true, message: '请选择退房时间' }]}
            getValueProps={(value?: string) => ({ value: value ? dayjs(value, 'HH:mm') : undefined })}
            normalize={(value?: Dayjs | null) => (value ? value.format('HH:mm') : '')}
          >
            <TimePicker format="HH:mm" minuteStep={30} style={{ width: 150 }} />
          </Form.Item>
          <Form.Item
            label="营业状态"
            name="status"
            getValueProps={(value?: number) => ({ checked: value === 1 })}
            normalize={(checked?: boolean) => (checked ? 1 : 0)}
          >
            <Switch checkedChildren="营业中" unCheckedChildren="暂停营业" />
          </Form.Item>
          <Form.Item label="酒店简介">
            <Form.Item name="description" noStyle>
              <Input.TextArea rows={3} maxLength={200} showCount />
            </Form.Item>
          </Form.Item>
        </Form>
      </Modal>

      <BookingDialog
        open={bookingOpen}
        hotel={currentHotel}
        hotels={hotels}
        onClose={() => setBookingOpen(false)}
        onSuccess={load}
      />
    </div>
  )
}
