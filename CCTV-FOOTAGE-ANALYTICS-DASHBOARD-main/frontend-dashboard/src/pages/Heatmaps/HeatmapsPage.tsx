import React from 'react';
import { PageHeader } from '../../components/layout';
import { HeatmapCard, HeatmapLegend } from '../../components/heatmaps';
import { Skeleton } from '../../components/ui';
import { useApiData } from '../../hooks';
import { API_BASE } from '../../constants';
import type { HeatmapData } from '../../types';

interface HeatmapsPageProps {
  storeId: string;
  storeName: string;
}

/**
 * Zone Heatmaps page — displays dwell-density heatmap cards for each zone,
 * sorted hottest first. Refreshes every 8 s.
 */
const HeatmapsPage: React.FC<HeatmapsPageProps> = ({ storeId, storeName }) => {
  const { data, loading } = useApiData<HeatmapData>(
    `${API_BASE}/stores/${storeId}/heatmap`,
    8000
  );

  return (
    <div className="page-fade-in" id="heatmaps-page">
      <PageHeader
        title={`Zone Heatmaps — ${storeName}`}
        subtitle="Aggregated ZONE_DWELL density per zone over the last 60 minutes. Refreshes every 8s."
      />

      {loading ? (
        <div className="heatmap-grid">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="heatmap-zone-card frosted-glass">
              <Skeleton height="12px" width="60%" />
              <div style={{ marginTop: 8 }}>
                <Skeleton height="36px" width="40%" />
              </div>
              <div style={{ marginTop: 12 }}>
                <Skeleton height="6px" />
              </div>
            </div>
          ))}
        </div>
      ) : !data?.zones?.length ? (
        <div className="no-data-state">
          <span className="icon">📭</span>
          <p>
            No zone data yet. The Event Engine will populate this as visitors dwell in zones.
          </p>
        </div>
      ) : (
        <>
          <HeatmapLegend />
          <div className="heatmap-grid">
            {data.zones
              .slice()
              .sort((a, b) => b.dwell_time_density - a.dwell_time_density)
              .map((zone, idx) => (
                <HeatmapCard key={zone.zone_id} zone={zone} rank={idx + 1} />
              ))}
          </div>
        </>
      )}
    </div>
  );
};

export default HeatmapsPage;
