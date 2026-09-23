import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  DatePicker,
  Descriptions,
  Form,
  Input,
  Modal,
  Select,
  Table,
  Tag,
  theme,
  type TableColumnsType,
} from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'

import { bookingApi, hotelApi } from '@/api'
import type { Booking, Hotel } from '@/api/types'
import { BOOKING_STATUS_COLOR, BOOKING_STATUS_TEXT } from '@/store/user'
import { feedback } from '@/utils/feedback'
import { money, stayRange } from '@/utils/format'

const PAGE_SIZE = 10
const DAY_FORMAT = 'YYYY-MM-DD'

const STATUS_OPTIONS = Object.entries(BOOKING_STATUS_TEXT).map(([value, label]) => ({ value, label }))

export default function OrderConfirm() {
  const [loading, setLoading] = useState(false)
  const { token } = theme.useToken()
  const [submitting, setSubmitting] = useState(false)
  const [records, setRecords] = useState<Booking[]>([])
  const [hotels, setHotels] = useState<Hotel[]>([])
  const [total, setTotal] = useState(0)
  const [keywordInput, setKeywordInput] = useState('')
  // 默认不限定状态：管理员既能一眼看到待确认订单（列表按待确认优先排序），也能看到已完成等历史订单
  const [query, setQuery] = useState<{
    status: string
    hotel_id: number | ''
    check_in_date: string
    keyword: string
    page: number
  }>({ status: '', hotel_id: '', check_in_date: '', keyword: '', page: 1 })

  const [reviewOpen, setReviewOpen] = useState(false)
  const [reviewRow, setReviewRow] = useState<Booking | null>(null)
  const [reviewAction, setReviewAction] = useState<'confirm' | 'reject'>('confirm')
  const [reviewForm] = Form.useForm<{ remark: string }>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await bookingApi.page({
        status: query.status,
        hotel_id: query.hotel_id,
        check_in_date: query.check_in_date,
        keyword: query.keyword,
        page: query.page,
        page_size: PAGE_SIZE,
      })
      setRecords(data.items)
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

  useEffect(() => {
    hotelApi
      .list({ page_size: 100 })
      .then((data) => setHotels(data.items))
      .catch(() => setHotels([]))
  }, [])

  const emptyText = query.status
    ? `没有「${BOOKING_STATUS_TEXT[query.status as keyof typeof BOOKING_STATUS_TEXT]}」的订单，选择「全部状态」可查看历史订单`
    : '暂无订单记录'

  const openReview = (row: Booking, action: 'confirm' | 'reject') => {
    setReviewRow(row)
    setReviewAction(action)
    reviewForm.setFieldsValue({ remark: action === 'confirm' ? '已确认，房间已保留' : '' })
    setReviewOpen(true)
  }

  const submitReview = async () => {
    if (!reviewRow) return
    const values = await reviewForm.validateFields().catch(() => null)
    if (!values) return
    setSubmitting(true)
    try {
      await bookingApi.review(reviewRow.id, { action: reviewAction, remark: values.remark || '' })
      feedback.success(reviewAction === 'confirm' ? '订单已确认' : '订单已拒绝')
      setReviewOpen(false)
      await load()
    } finally {
      setSubmitting(false)
    }
  }

  const cancel = (row: Booking) => {
    feedback.confirm({
      title: '提示',
      content: `确定取消「${row.user_name}」在「${row.hotel_name}」的订单吗？`,
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await bookingApi.cancel(row.id)
        feedback.success('订单已取消')
        await load()
      },
    })
  }

  const remove = (row: Booking) => {
    feedback.confirm({
      title: '提示',
      content: '删除后不可恢复，确定删除该订单吗？',
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await bookingApi.remove(row.id)
        feedback.success('删除成功')
        await load()
      },
    })
  }

  const columns: TableColumnsType<Booking> = [
    {
      title: '会员',
      width: 110,
      render: (_, row) => (
        <div>
          <div>{row.user_name}</div>
          <div style={{ color: token.colorTextTertiary, fontSize: 12 }}>{row.username}</div>
        </div>
      ),
    },
    {
      title: '酒店 / 房型',
      width: 190,
      ellipsis: true,
      render: (_, row) => (
        <div>
          <div>{row.hotel_name}</div>
          <div style={{ color: token.colorTextTertiary, fontSize: 12 }}>{row.room_type_name}</div>
        </div>
      ),
    },
    { title: '入住 / 退房', width: 180, render: (_, row) => stayRange(row) },
    { title: '间数 / 人数', width: 100, render: (_, row) => `${row.rooms} 间 / ${row.guests} 人` },
    { title: '总价', width: 90, render: (_, row) => money(row.total_amount) },
    {
      title: '状态',
      width: 90,
      render: (_, row) => <Tag color={BOOKING_STATUS_COLOR[row.status]}>{row.status_text}</Tag>,
    },
    { title: '确认意见', dataIndex: 'remark', width: 140, ellipsis: true, render: (value: string) => value || '-' },
    {
      title: '操作',
      width: 180,
      fixed: 'right',
      render: (_, row) => (
        <>
          {row.status === 'pending' && (
            <>
              <Button type="link" style={{ color: token.colorSuccess }} onClick={() => openReview(row, 'confirm')}>
                确认
              </Button>
              <Button type="link" danger onClick={() => openReview(row, 'reject')}>
                拒绝
              </Button>
            </>
          )}
          {(row.status === 'pending' || row.status === 'confirmed') && (
            <Button type="link" style={{ color: token.colorWarning }} onClick={() => cancel(row)}>
              取消
            </Button>
          )}
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
          <div className="page-title">订单确认</div>
          <div className="page-toolbar">
            <Select
              value={query.status === '' ? undefined : query.status}
              placeholder="全部状态"
              allowClear
              style={{ width: 140 }}
              options={STATUS_OPTIONS}
              onChange={(value) => setQuery((prev) => ({ ...prev, status: value ?? '', page: 1 }))}
            />
            <Select
              value={query.hotel_id === '' ? undefined : query.hotel_id}
              placeholder="全部酒店"
              allowClear
              style={{ width: 190 }}
              options={hotels.map((item) => ({ value: item.id, label: item.name }))}
              onChange={(value) => setQuery((prev) => ({ ...prev, hotel_id: value ?? '', page: 1 }))}
            />
            <DatePicker
              value={query.check_in_date ? dayjs(query.check_in_date, DAY_FORMAT) : null}
              placeholder="入住日期"
              style={{ width: 160 }}
              onChange={(value: Dayjs | null) =>
                setQuery((prev) => ({
                  ...prev,
                  check_in_date: value ? value.format(DAY_FORMAT) : '',
                  page: 1,
                }))
              }
            />
            <Input.Search
              value={keywordInput}
              placeholder="搜索会员"
              allowClear
              style={{ width: 170 }}
              onChange={(event) => setKeywordInput(event.target.value)}
              onSearch={() => setQuery((prev) => ({ ...prev, keyword: keywordInput, page: 1 }))}
            />
            <Button icon={<ReloadOutlined />} onClick={() => setQuery((prev) => ({ ...prev }))}>
              刷新
            </Button>
          </div>
        </div>
      </Card>

      <Card variant="borderless" style={{ marginTop: 16 }}>
        <Table<Booking>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={records}
          scroll={{ x: 1080 }}
          locale={{ emptyText }}
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

      <Modal
        title={reviewAction === 'confirm' ? '确认订单' : '拒绝订单'}
        open={reviewOpen}
        width={500}
        okText={`确定${reviewAction === 'confirm' ? '确认' : '拒绝'}`}
        cancelText="取消"
        confirmLoading={submitting}
        onOk={submitReview}
        onCancel={() => setReviewOpen(false)}
      >
        <Descriptions
          column={1}
          bordered
          size="small"
          style={{ marginTop: 20, marginBottom: 16 }}
          items={[
            { key: 'hotel', label: '酒店', children: reviewRow?.hotel_name },
            { key: 'room', label: '房型', children: reviewRow?.room_type_name },
            { key: 'user', label: '会员', children: reviewRow?.user_name },
            {
              key: 'dates',
              label: '入住 / 退房',
              children: reviewRow ? stayRange(reviewRow) : '',
            },
            {
              key: 'rooms',
              label: '间数 / 人数',
              children: reviewRow ? `${reviewRow.rooms} 间 / ${reviewRow.guests} 人` : '',
            },
            { key: 'amount', label: '总价', children: money(reviewRow?.total_amount) },
          ]}
        />
        <Form form={reviewForm} layout="vertical">
          <Form.Item label="确认意见" name="remark">
            <Input.TextArea rows={3} maxLength={255} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
