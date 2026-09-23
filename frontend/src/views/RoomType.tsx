import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Table,
  Tag,
  type TableColumnsType,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'

import { hotelApi, roomTypeApi } from '@/api'
import type { Hotel, RoomType as RoomTypeRecord, RoomTypePayload, RoomTypeStatus } from '@/api/types'
import { ROOM_TYPE_STATUS_COLOR, ROOM_TYPE_STATUS_TEXT } from '@/store/user'
import { feedback } from '@/utils/feedback'
import { money } from '@/utils/format'

const PAGE_SIZE = 10

const STATUS_OPTIONS = Object.entries(ROOM_TYPE_STATUS_TEXT).map(([value, label]) => ({ value, label }))

export default function RoomType() {
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [records, setRecords] = useState<RoomTypeRecord[]>([])
  const [hotels, setHotels] = useState<Hotel[]>([])
  const [total, setTotal] = useState(0)
  const [keywordInput, setKeywordInput] = useState('')
  const [query, setQuery] = useState<{
    keyword: string
    hotel_id: number | ''
    status: RoomTypeStatus | ''
    page: number
  }>({ keyword: '', hotel_id: '', status: '', page: 1 })

  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form] = Form.useForm<RoomTypePayload>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await roomTypeApi.page({
        keyword: query.keyword,
        hotel_id: query.hotel_id,
        status: query.status,
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

  const openForm = (row?: RoomTypeRecord) => {
    setEditingId(row?.id ?? null)
    form.setFieldsValue({
      name: row?.name || '',
      code: row?.code || '',
      bed_type: row?.bed_type || '',
      hotel_id: row?.hotel_id ?? (query.hotel_id || hotels[0]?.id),
      price: row?.price ?? 0,
      capacity: row?.capacity ?? 2,
      quantity: row?.quantity ?? 10,
      status: row?.status || 'open',
      description: row?.description || '',
    })
    setFormOpen(true)
  }

  const submitForm = async () => {
    const values = await form.validateFields().catch(() => null)
    if (!values) return
    setSubmitting(true)
    try {
      if (editingId) await roomTypeApi.update(editingId, values)
      else await roomTypeApi.create(values)
      feedback.success('保存成功')
      setFormOpen(false)
      await load()
    } finally {
      setSubmitting(false)
    }
  }

  const remove = (row: RoomTypeRecord) => {
    feedback.confirm({
      title: '提示',
      content: `确定删除房型「${row.name}」吗？`,
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await roomTypeApi.remove(row.id)
        feedback.success('删除成功')
        await load()
      },
    })
  }

  const columns: TableColumnsType<RoomTypeRecord> = [
    { title: '房型名称', dataIndex: 'name', width: 130, ellipsis: true },
    { title: '房型编号', dataIndex: 'code', width: 120 },
    { title: '床型', dataIndex: 'bed_type', width: 130, ellipsis: true },
    { title: '所属酒店', dataIndex: 'hotel_name', width: 170, ellipsis: true },
    { title: '价格/晚', width: 100, render: (_, row) => money(row.price) },
    { title: '可住人数', dataIndex: 'capacity', width: 100 },
    { title: '房量', dataIndex: 'quantity', width: 80 },
    {
      title: '状态',
      width: 100,
      render: (_, row) => <Tag color={ROOM_TYPE_STATUS_COLOR[row.status]}>{ROOM_TYPE_STATUS_TEXT[row.status]}</Tag>,
    },
    { title: '说明', dataIndex: 'description', width: 160, ellipsis: true },
    {
      title: '操作',
      width: 130,
      fixed: 'right',
      render: (_, row) => (
        <>
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
          <div className="page-title">房型管理</div>
          <div className="page-toolbar">
            <Input.Search
              value={keywordInput}
              placeholder="搜索房型名称/编号/床型"
              allowClear
              style={{ width: 220 }}
              onChange={(event) => setKeywordInput(event.target.value)}
              onSearch={() => setQuery((prev) => ({ ...prev, keyword: keywordInput, page: 1 }))}
            />
            <Select
              value={query.hotel_id === '' ? undefined : query.hotel_id}
              placeholder="全部酒店"
              allowClear
              style={{ width: 190 }}
              options={hotels.map((item) => ({ value: item.id, label: item.name }))}
              onChange={(value) => setQuery((prev) => ({ ...prev, hotel_id: value ?? '', page: 1 }))}
            />
            <Select
              value={query.status === '' ? undefined : query.status}
              placeholder="全部状态"
              allowClear
              style={{ width: 140 }}
              options={STATUS_OPTIONS}
              onChange={(value) => setQuery((prev) => ({ ...prev, status: value ?? '', page: 1 }))}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => openForm()}>
              新增房型
            </Button>
          </div>
        </div>
      </Card>

      <Card variant="borderless" style={{ marginTop: 16 }}>
        <Table<RoomTypeRecord>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={records}
          scroll={{ x: 1300 }}
          locale={{ emptyText: '暂无房型数据' }}
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
        title={editingId ? '编辑房型' : '新增房型'}
        open={formOpen}
        width={540}
        okText="保存"
        cancelText="取消"
        confirmLoading={submitting}
        onOk={submitForm}
        onCancel={() => setFormOpen(false)}
      >
        <Form form={form} labelCol={{ span: 6 }} wrapperCol={{ span: 18 }} style={{ marginTop: 20 }}>
          <Form.Item label="房型名称" name="name" rules={[{ required: true, message: '请输入房型名称' }]}>
            <Input placeholder="例如：高级大床房" />
          </Form.Item>
          <Form.Item label="房型编号" name="code">
            <Input placeholder="例如：RT-HZ-001" />
          </Form.Item>
          <Form.Item label="床型" name="bed_type">
            <Input placeholder="例如：1.8m 大床 / 1.2m 双床" />
          </Form.Item>
          <Form.Item label="所属酒店" name="hotel_id" rules={[{ required: true, message: '请选择所属酒店' }]}>
            <Select
              placeholder="请选择酒店"
              options={hotels.map((item) => ({ value: item.id, label: item.name }))}
            />
          </Form.Item>
          <Form.Item label="价格/晚" name="price">
            <InputNumber min={0} max={99999} step={50} />
          </Form.Item>
          <Form.Item label="可住人数" name="capacity">
            <InputNumber min={1} max={20} />
          </Form.Item>
          <Form.Item label="房量（间）" name="quantity" rules={[{ required: true, message: '请输入房量' }]}>
            <InputNumber min={1} max={999} />
          </Form.Item>
          <Form.Item label="状态" name="status" rules={[{ required: true, message: '请选择状态' }]}>
            <Select options={STATUS_OPTIONS} />
          </Form.Item>
          <Form.Item label="说明">
            <Form.Item name="description" noStyle>
              <Input.TextArea rows={3} maxLength={200} showCount />
            </Form.Item>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
