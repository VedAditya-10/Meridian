import React from 'react';
import { PageHeader } from '../../components/layout';
import { AnomalyCard } from '../../components/anomalies';
import { Skeleton } from '../../components/ui';
import { useApiData } from '../../hooks';
import { API_BASE } from '../../constants';
import type { Anomaly } from '../../types';

interface AnomaliesPageProps {
  storeId: string;
  storeName: string;
}

/**
 * Anomaly Detection page — lists active statistical anomalies or shows
 * an "all clear" state. Refreshes every 15 s.
 */
const AnomaliesPage: React.FC<AnomaliesPageProps> = ({ storeId, storeName }) => {
  const { data, loading } = useApiData<Anomaly[]>(
    `${API_BASE}/stores/${storeId}/anomalies`,
    15000
  );

  return (
    <div className="page-fade-in" id="anomalies-page">
      <PageHeader
        title={`Anomaly Detection — ${storeName}`}
        subtitle="Statistical heuristics scanning queue spikes, conversion drops, and dead feeds. Refreshes every 15s."
      />

      {loading ? (
        <div className="anomaly-list">
          {[1, 2].map((i) => (
            <div key={i} className="anomaly-card high">
              <Skeleton width="36px" height="36px" />
              <div style={{ flex: 1 }}>
                <Skeleton height="18px" width="40%" />
                <div style={{ marginTop: 8 }}>
                  <Skeleton height="14px" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : data?.length ? (
        <div className="anomaly-list">
          {data.map((anomaly, i) => (
            <AnomalyCard key={i} anomaly={anomaly} index={i} />
          ))}
        </div>
      ) : (
        <div className="all-clear-state">
          <div className="all-clear-icon">✅</div>
          <div className="all-clear-title">All Systems Normal</div>
          <div className="all-clear-sub">
            No anomalies detected for {storeName}. Queue abandonment and conversion rates are
            within thresholds.
          </div>
        </div>
      )}
    </div>
  );
};

export default AnomaliesPage;
