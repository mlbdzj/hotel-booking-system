import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Col, Row, Table, Tag, type TableColumnsType } from 'antd'
import {
  BankOutlined,
  CalendarOutlined,
  PayCircleOutlined,
  StarOutlined,
  TeamOutlined,
} from '@ant-design/icons'

import { statsApi } from '@/api'
import type { Booking, StatOverview } from '@/api/types'
import { BOOKING_STATUS_COLOR, useUserStore } from '@/store/user'
import { money, stayRange } from '@/utils/format'

const EMPTY_OVERVIEW: StatOverview = {
  hotel_total: 0,
  room_type_total: 0,
  user_total: 0,
  booking_total: 0,
  pending_total: 0,
  today_check_in_total: 0,
  occupancy_rate: 0,
  week_total: 0,
  week_start: '',
  week_end: '',
  hotel_ranking: [],
  recent_bookings: [],
}

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 6) return '凌晨好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

function rankColor(index: number): string {
  if (index === 0) return '#e6a23c'
  if (index === 1) return '#409eff'
  return '#909399'
}

export default function Home() {
  const navigate = useNavigate()
  const user = useUserStore((state) => state.user)
  const isAdmin = user?.role === 'admin'
  const displayName = user?.name || user?.username || '用户'

  const [loading, setLoading] = useState(false)
  const [overview, setOverview] = useState<StatOverview>(EMPTY_OVERVIEW)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setOverview(await statsApi.overview())
    } catch {
      // 请求层已经提示过错误
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const weekText = (() => {
    const { week_start: start, week_end: end } = overview
    if (!start || !end) return ''
    const short = (value: string) => String(value).slice(5).replace('-', '/')
    return `${short(start)} ~ ${short(end)}`
  })()

  const cards = isAdmin
    ? [
        { label: '门店数', value: overview.hotel_total, icon: <BankOutlined />, color: '#409eff', tip: '在营酒店门店' },
        { label: '房型数', value: overview.room_type_total, icon: <StarOutlined />, color: '#67c23a', tip: '可预订房型数量' },
        { label: '会员数', value: overview.user_total, icon: <TeamOutlined />, color: '#e6a23c', tip: '注册会员总数' },
        { label: '待确认订单', value: overview.pending_total, icon: <CalendarOutlined />, color: '#f56c6c', tip: '等待确认的订单' },
      ]
    : [
        { label: '门店数', value: overview.hotel_total, icon: <BankOutlined />, color: '#409eff', tip: '在营酒店门店' },
        { label: '房型数', value: overview.room_type_total, icon: <StarOutlined />, color: '#67c23a', tip: '可预订房型数量' },
        { label: '我的订单', value: overview.booking_total, icon: <CalendarOutlined />, color: '#e6a23c', tip: '累计订单数' },
        { label: '今日入住', value: overview.today_check_in_total, icon: <PayCircleOutlined />, color: '#f56c6c', tip: '今天入住的订单' },
      ]

  const columns: TableColumnsType<Booking> = [
    {
      title: '酒店 / 房型',
      dataIndex: 'hotel_name',
      width: 200,
      ellipsis: true,
      render: (_, row) => (
        <div>
          <div>{row.hotel_name}</div>
          <div style={{ color: '#909399', fontSize: 12 }}>{row.room_type_name}</div>
        </div>
      ),
    },
    ...(isAdmin
      ? [{ title: '会员', dataIndex: 'user_name' as const, width: 90 }]
      : []),
    { title: '入住 / 退房', width: 200, render: (_, row) => stayRange(row) },
    { title: '总价', width: 90, render: (_, row) => money(row.total_amount) },
    {
      title: '状态',
      width: 100,
      render: (_, row) => <Tag color={BOOKING_STATUS_COLOR[row.status]}>{row.status_text}</Tag>,
    },
  ]

  return (
    <div>
      <Card variant="borderless" style={{ marginBottom: 16 }} loading={loading}>
        <div className="page-block-head">
          <div>
            <div style={{ fontSize: 18, fontWeight: 'bold' }}>
              {greeting()}，{displayName}
            </div>
            <div style={{ marginTop: 6, color: '#909399' }}>
              {isAdmin
                ? '这里是酒店经营总览，您可以确认订单并维护酒店与房型。'
                : '您可以预订酒店、查看订单进度，也可以直接问客服助手。'}
            </div>
          </div>
          <div className="page-toolbar">
            <Button type="primary" icon={<BankOutlined />} onClick={() => navigate('/manager/hotel')}>
              预订酒店
            </Button>
            <Button onClick={() => navigate('/manager/booking')}>我的订单</Button>
            {isAdmin && (
              <Button color="gold" variant="solid" onClick={() => navigate('/manager/order-confirm')}>
                订单确认
              </Button>
            )}
          </div>
        </div>
      </Card>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        {cards.map((card) => (
          <Col key={card.label} xs={12} sm={12} md={6}>
            <Card variant="borderless" style={{ marginBottom: 16 }} loading={loading}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ color: '#909399', fontSize: 13 }}>{card.label}</div>
                  <div style={{ fontSize: 26, fontWeight: 'bold', marginTop: 6 }}>{card.value}</div>
                </div>
                <span style={{ fontSize: 38, color: card.color, lineHeight: 1 }}>{card.icon}</span>
              </div>
              <div style={{ marginTop: 8, color: '#909399', fontSize: 12 }}>{card.tip}</div>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16}>
        <Col xs={24} md={10}>
          <Card
            variant="borderless"
            loading={loading}
            style={{ marginBottom: 16 }}
            title="门店订单排行"
            extra={<span style={{ fontSize: 12, color: '#909399' }}>本周 {weekText}</span>}
          >
            {overview.hotel_ranking.length === 0 && <div style={{ color: '#909399' }}>暂无数据</div>}
            {overview.hotel_ranking.map((item, index) => (
              <div
                key={item.hotel_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '9px 0',
                  borderBottom: '1px solid #f2f3f5',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ color: rankColor(index), fontWeight: 'bold', width: 16 }}>{index + 1}</span>
                  <span>{item.hotel_name}</span>
                </div>
                <span style={{ color: '#606266' }}>{item.booking_count} 单</span>
              </div>
            ))}
            <div style={{ marginTop: 12, color: '#909399', fontSize: 12 }}>
              今日入住率 <b style={{ color: '#409eff' }}>{overview.occupancy_rate}%</b>
              （在住 {overview.occupancy_rate ? '中' : '—'}），排行按本周入住订单数统计，已取消 / 已拒绝不计入。
            </div>
          </Card>
        </Col>

        <Col xs={24} md={14}>
          <Card variant="borderless" title="最近订单" loading={loading}>
            <Table<Booking>
              rowKey="id"
              size="small"
              loading={loading}
              columns={columns}
              dataSource={overview.recent_bookings}
              pagination={false}
              locale={{ emptyText: '暂无订单记录' }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
