import React from 'react';
import { PageHeader } from '../../components/layout';
import { MetricCard, FunnelChart, SessionSummary, FootfallAndExitsChart, ProductEngagementChart } from '../../components/dashboard';
import { useApiData } from '../../hooks';
import { formatCurrency } from '../../utils';
import { API_BASE } from '../../constants';
import type { DashboardMetrics, FunnelData } from '../../types';

interface OverviewPageProps {
  storeId: string;
  storeName: string;
}

/**
 * Overview page — live KPI metrics, conversion funnel, and session summary.
 * All data is polled every 2 s.
 */
const OverviewPage: React.FC<OverviewPageProps> = ({ storeId, storeName }) => {
  const { data: metrics, loading } = useApiData<DashboardMetrics>(
    `${API_BASE}/dashboard/store/${storeId}`,
    2000
  );
  const { data: funnel, loading: funnelLoading } = useApiData<FunnelData>(
    `${API_BASE}/stores/${storeId}/funnel`,
    2000
  );

  return (
    <div className="page-fade-in" id="overview-page">
      <PageHeader
        title={`Live Overview — ${storeName}`}
        subtitle="Real-time CCTV Analytics combined with POS Transactions."
      />

      <div className="metrics-grid">
        <MetricCard
          id="metric-footfall"
          icon="🚪"
          title="Footfall"
          value={loading ? '—' : `${metrics?.footfall ?? 0}`}
          loading={loading}
        />
        <MetricCard
          id="metric-unique"
          icon="🧑‍🤝‍🧑"
          title="Unique Visitors"
          value={loading ? '—' : `${metrics?.uniqueVisitors ?? 0}`}
          loading={loading}
        />
        <MetricCard
          id="metric-transactions"
          icon="🛒"
          title="Transactions"
          value={loading ? '—' : `${metrics?.transactions ?? 0}`}
          loading={loading}
        />
        <MetricCard
          id="metric-gmv"
          icon="💰"
          title="GMV"
          value={loading ? '—' : formatCurrency(metrics?.gmv ?? 0)}
          positive
          delta="Live"
          loading={loading}
        />
        <MetricCard
          id="metric-conversion"
          icon="💳"
          title="Conversion Rate"
          value={loading ? '—' : `${(metrics?.conversionRate ?? 0).toFixed(1)}%`}
          positive
          loading={loading}
        />
        <MetricCard
          id="metric-abv"
          icon="🛍️"
          title="Avg Basket Value"
          value={loading ? '—' : formatCurrency(metrics?.averageBasketValue ?? 0)}
          loading={loading}
        />
      </div>

      <div className="charts-row">
        <FootfallAndExitsChart storeId={storeId} metrics={metrics} />
        <ProductEngagementChart storeId={storeId} />
      </div>

      <div className="charts-row">
        <FunnelChart data={funnel} loading={funnelLoading} />
        <SessionSummary metrics={metrics} loading={loading} />
      </div>
    </div>
  );
};

export default OverviewPage;
