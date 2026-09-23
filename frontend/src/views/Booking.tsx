import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Select, Table, Tag, theme, type TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'

import { bookingApi, hotelApi } from '@/api'
import type { Booking as BookingRecord, Hotel } from '@/api/types'
import BookingDialog from '@/components/BookingDialog'
import { BOOKING_STATUS_COLOR, BOOKING_STATUS_TEXT } from '@/store/user'
import { feedback } from '@/utils/feedback'
import { money, stayRange } from '@/utils/format'

const PAGE_SIZE = 10

const STATUS_OPTIONS = Object.entries(BOOKING_STATUS_TEXT).map(([value, label]) => ({ value, label }))

export default function Booking() {
  const [loading, setLoading] = useState(false)
  const { token } = theme.useToken()
  const [records, setRecords] = useState<BookingRecord[]>([])
  const [total, setTotal] = useState(0)
  const [hotels, setHotels] = useState<Hotel[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await bookingApi.my({ status, page, page_size: PAGE_SIZE })
      setRecords(data.items)
      setTotal(data.total)
    } catch {
      // 请求层已经提示过错误
    } finally {
      setLoading(false)
    }
  }, [page, status])

  const loadHotels = useCallback(async () => {
    try {
      const data = await hotelApi.list({ page_size: 100, status: 1 })
      setHotels(data.items)
    } catch {
      // 请求层已经提示过错误
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void loadHotels()
  }, [loadHotels])

  const cancel = (row: BookingRecord) => {
    feedback.confirm({
      title: '提示',
      content: `确定取消「${row.hotel_name} ${row.room_type_name}」的订单吗？`,
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await bookingApi.cancel(row.id)
        feedback.success('订单已取消')
        await load()
      },
    })
  }

  const columns: TableColumnsType<BookingRecord> = [
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
    { title: '间数 / 人数', width: 110, render: (_, row) => `${row.rooms} 间 / ${row.guests} 人` },
    { title: '总价', width: 100, render: (_, row) => money(row.total_amount) },
    {
      title: '特殊要求',
      dataIndex: 'special_request',
      width: 140,
      ellipsis: true,
      render: (value: string) => value || '-',
    },
    {
      title: '状态',
      width: 100,
      render: (_, row) => <Tag color={BOOKING_STATUS_COLOR[row.status]}>{row.status_text}</Tag>,
    },
    {
      title: '确认意见',
      dataIndex: 'remark',
      width: 150,
      ellipsis: true,
      render: (value: string) => value || '-',
    },
    {
      title: '操作',
      width: 110,
      fixed: 'right',
      render: (_, row) =>
        row.status === 'pending' || row.status === 'confirmed' ? (
          <Button type="link" danger onClick={() => cancel(row)}>
            取消订单
          </Button>
        ) : (
          <span style={{ color: token.colorTextQuaternary }}>-</span>
        ),
    },
  ]

  return (
    <div>
      <Card variant="borderless">
        <div className="page-block-head">
          <div className="page-title">我的订单</div>
          <div className="page-toolbar">
            <Select
              value={status}
              placeholder="全部状态"
              allowClear
              style={{ width: 150 }}
              options={STATUS_OPTIONS}
              onChange={(value) => setStatus(value ?? '')}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setDialogOpen(true)}>
              预订酒店
            </Button>
          </div>
        </div>
      </Card>

      <Card variant="borderless" style={{ marginTop: 16 }}>
        <Table<BookingRecord>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={records}
          scroll={{ x: 1080 }}
          locale={{ emptyText: '暂无订单，去「酒店管理」预订一间吧' }}
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total,
            showSizeChanger: false,
            showTotal: (value) => `共 ${value} 条`,
            onChange: setPage,
          }}
        />
      </Card>

      <BookingDialog
        open={dialogOpen}
        hotels={hotels}
        onClose={() => setDialogOpen(false)}
        onSuccess={load}
      />
    </div>
  )
}
