import React from 'react';

interface SkeletonProps {
  width?: string;
  height?: string;
}

/**
 * Generic loading skeleton placeholder.
 */
export const Skeleton: React.FC<SkeletonProps> = ({
  width = '100%',
  height = '24px',
}) => <div className="skeleton" style={{ width, height }} />;
