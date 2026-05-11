'use client'

import React, { useEffect, useState, useMemo } from 'react';
import { DocRouterAccountApi } from '@/utils/api';
import { UsageRangeRequest, UsageRangeResponse, UsageDataPoint } from '@/types/payments';
import { toast } from 'react-toastify';
import { formatLocalDate } from '@/utils/date';

interface SubscriptionSPUUsageChartProps {
  organizationId: string;
  refreshKey?: number;
  defaultBillingPeriod?: {
    start: string;
    end: string;
  };
}

interface OperationBreakdown {
  operation: string;
  spus: number;
}

interface ProcessedDataPoint {
  date: string;
  spus: number;
  cumulative_spus: number;
  breakdown: OperationBreakdown[];
}

const OPERATION_COLORS: Record<string, { bar: string; label: string }> = {
  ocr:          { bar: 'bg-blue-500',   label: 'OCR' },
  document_llm: { bar: 'bg-green-500',  label: 'Document LLM' },
  agent_llm:    { bar: 'bg-purple-500', label: 'Agent LLM' },
};

// Normalize legacy operation names before lookup
const normalizeOperation = (op: string): string => {
  if (op === 'document_processing') return 'document_llm';
  return op;
};

const operationColor = (op: string) => {
  const normalized = normalizeOperation(op);
  return OPERATION_COLORS[normalized] ?? { bar: 'bg-gray-400', label: normalized };
};

const SubscriptionSPUUsageChart: React.FC<SubscriptionSPUUsageChartProps> = ({ organizationId, refreshKey, defaultBillingPeriod }) => {
  const [rangeData, setRangeData] = useState<UsageRangeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [granularity, setGranularity] = useState<'daily' | 'monthly'>('daily');
  const [processedData, setProcessedData] = useState<ProcessedDataPoint[]>([]);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  
  // Date range state
  const getCurrentBillingPeriod = () => {
    const now = new Date();
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    
    // Use local date formatting to avoid timezone issues
    const localDate = (date: Date) => {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    };
    
    return {
      start: localDate(startOfMonth),
      end: localDate(endOfMonth)
    };
  };
  
  const [dateRange, setDateRange] = useState(() => {
    // Use default billing period if provided, otherwise fall back to current month
    return defaultBillingPeriod || getCurrentBillingPeriod();
  });
  const [isCustomRange, setIsCustomRange] = useState(false);
  const [activePreset, setActivePreset] = useState<string>('current_month');

  // Update date range when default billing period changes
  useEffect(() => {
    if (defaultBillingPeriod && !isCustomRange) {
      setDateRange(defaultBillingPeriod);
    }
  }, [defaultBillingPeriod, isCustomRange]);

  // Single useEffect that handles both initial fetch and refresh
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        const request: UsageRangeRequest = {
          start_date: dateRange.start,
          end_date: dateRange.end
        };
        
        const response = await docRouterAccountApi.getUsageRange(organizationId, request);
        setRangeData(response);
      } catch (error) {
        console.error('Error fetching usage range:', error);
        toast.error('Failed to load usage range data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [organizationId, refreshKey, dateRange, docRouterAccountApi]);

  useEffect(() => {
    if (rangeData) {
      const processData = (data: UsageDataPoint[]) => {
        if (!data || data.length === 0) return [];

        const sortedData = [...data].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

        // Group by date key (daily → YYYY-MM-DD, monthly → YYYY-MM)
        const groupMap = new Map<string, { dateKey: string; breakdown: Map<string, number> }>();

        sortedData.forEach(point => {
          const date = new Date(point.date);
          const key = granularity === 'daily'
            ? point.date
            : `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;

          if (!groupMap.has(key)) {
            groupMap.set(key, { dateKey: granularity === 'daily' ? point.date : `${key}-01`, breakdown: new Map() });
          }
          const entry = groupMap.get(key)!;
          const op = normalizeOperation(point.operation);
          entry.breakdown.set(op, (entry.breakdown.get(op) ?? 0) + point.spus);
        });

        let cumulative = 0;
        return Array.from(groupMap.values()).map(({ dateKey, breakdown }) => {
          const total = Array.from(breakdown.values()).reduce((s, v) => s + v, 0);
          cumulative += total;
          return {
            date: dateKey,
            spus: total,
            cumulative_spus: cumulative,
            breakdown: Array.from(breakdown.entries())
              .map(([operation, spus]) => ({ operation, spus }))
              .sort((a, b) => a.operation.localeCompare(b.operation)),
          };
        });
      };

      const processed = processData(rangeData.data_points);
      setProcessedData(processed);
    }
  }, [rangeData, granularity]);

  const parseLocalDate = (dateStr: string) => {
    const [year, month, day] = dateStr.split('-').map(Number);
    return new Date(year, month - 1, day);
  };

  const formatChartDate = (dateStr: string) => formatLocalDate(parseLocalDate(dateStr));

  const formatPeriod = () => {
    const startDate = parseLocalDate(dateRange.start);
    const endDate = parseLocalDate(dateRange.end);
    
    const startStr = formatLocalDate(startDate);
    const endStr = formatLocalDate(endDate);
    
    // Determine the correct label based on active preset or custom range
    let label = '';
    if (isCustomRange) {
      label = 'Custom Range';
    } else {
      switch (activePreset) {
        case 'current_month':
          label = 'Current Period';
          break;
        case 'last_month':
          label = 'Previous Period';
          break;
        case 'last_30_days':
          label = 'Last 30 Days';
          break;
        case 'last_90_days':
          label = 'Last 90 Days';
          break;
        default:
          label = 'Selected Period';
      }
    }
    
    return `${startStr} - ${endStr} (${label})`;
  };

  const handlePresetRange = (preset: string) => {
    const now = new Date();
    let start: Date, end: Date;
    
    // Helper function for local date formatting
    const localDate = (date: Date) => {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    };
    
    // Helper function to get billing period dates
    const getBillingPeriodDates = () => {
      if (defaultBillingPeriod) {
        return {
          start: new Date(defaultBillingPeriod.start),
          end: new Date(defaultBillingPeriod.end)
        };
      }
      // Fallback to current month if no billing period
      return {
        start: new Date(now.getFullYear(), now.getMonth(), 1),
        end: new Date(now.getFullYear(), now.getMonth() + 1, 0)
      };
    };
    
    switch (preset) {
      case 'current_month':
        // Use the current billing period
        const currentBilling = getBillingPeriodDates();
        start = currentBilling.start;
        end = currentBilling.end;
        setIsCustomRange(false);
        break;
      case 'last_month':
        // Calculate previous billing period
        const currentBillingForLast = getBillingPeriodDates();
        const billingDuration = currentBillingForLast.end.getTime() - currentBillingForLast.start.getTime();
        end = new Date(currentBillingForLast.start.getTime() - 1); // End of previous period
        start = new Date(end.getTime() - billingDuration); // Start of previous period
        setIsCustomRange(false);
        break;
      case 'last_30_days':
        end = new Date(now);
        start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        setIsCustomRange(false);
        break;
      case 'last_90_days':
        end = new Date(now);
        start = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
        setIsCustomRange(false);
        break;
      default:
        return;
    }
    
    setActivePreset(preset);
    setDateRange({
      start: localDate(start),
      end: localDate(end)
    });
  };

  if (loading) {
    return (
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }


  const maxValue = Math.max(...processedData.map(dp => dp.spus));
  

  // Calculate average over the entire date range
  const getDateRangeDays = () => {
    const startDate = new Date(dateRange.start);
    const endDate = new Date(dateRange.end);
    const timeDiff = endDate.getTime() - startDate.getTime();
    return Math.ceil(timeDiff / (1000 * 3600 * 24)) + 1; // +1 to include both start and end dates
  };

  const getDateRangeMonths = () => {
    const startDate = new Date(dateRange.start);
    const endDate = new Date(dateRange.end);
    const yearDiff = endDate.getFullYear() - startDate.getFullYear();
    const monthDiff = endDate.getMonth() - startDate.getMonth();
    return Math.max(1, yearDiff * 12 + monthDiff + 1); // +1 to include both start and end months
  };

  const averageSpus = rangeData ? (
    granularity === 'daily' 
      ? rangeData.total_spus / getDateRangeDays()
      : rangeData.total_spus / getDateRangeMonths()
  ) : 0;

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">SPU Usage Range</h3>
          <p className="text-sm text-gray-600 mt-1">
            {formatPeriod()}
          </p>
        </div>
        
        {/* Controls */}
        <div className="flex flex-col sm:flex-row gap-3 mt-4 sm:mt-0">
          <div className="flex rounded-md shadow-sm">
            <button
              onClick={() => setGranularity('daily')}
              className={`px-3 py-2 text-sm font-medium rounded-l-md border ${
                granularity === 'daily'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              Daily
            </button>
            <button
              onClick={() => setGranularity('monthly')}
              className={`px-3 py-2 text-sm font-medium rounded-r-md border-t border-r border-b ${
                granularity === 'monthly'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              Monthly
            </button>
          </div>
        </div>
      </div>

      {/* Date Range Controls */}
      <div className="mb-4 p-4 bg-gray-50 rounded-lg">
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
          {/* Preset buttons */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handlePresetRange('current_month')}
              className={`px-3 py-1 text-xs font-medium rounded border ${
                !isCustomRange && activePreset === 'current_month'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white border-gray-300 hover:bg-gray-50'
              }`}
            >
              Current Period
            </button>
            <button
              onClick={() => handlePresetRange('last_month')}
              className={`px-3 py-1 text-xs font-medium rounded border ${
                !isCustomRange && activePreset === 'last_month'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white border-gray-300 hover:bg-gray-50'
              }`}
            >
              Previous Period
            </button>
            <button
              onClick={() => handlePresetRange('last_30_days')}
              className={`px-3 py-1 text-xs font-medium rounded border ${
                !isCustomRange && activePreset === 'last_30_days'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white border-gray-300 hover:bg-gray-50'
              }`}
            >
              Last 30 Days
            </button>
            <button
              onClick={() => handlePresetRange('last_90_days')}
              className={`px-3 py-1 text-xs font-medium rounded border ${
                !isCustomRange && activePreset === 'last_90_days'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white border-gray-300 hover:bg-gray-50'
              }`}
            >
              Last 90 Days
            </button>
          </div>
          
          {/* Custom date inputs */}
          <div className="flex items-center gap-2 ml-auto">
            <label className="text-sm text-gray-600">From:</label>
            <input
              type="date"
              value={dateRange.start}
              onChange={(e) => {
                setDateRange(prev => ({ ...prev, start: e.target.value }));
                setIsCustomRange(true);
                setActivePreset('');
              }}
              className="px-2 py-1 text-sm border border-gray-300 rounded"
            />
            <label className="text-sm text-gray-600">To:</label>
            <input
              type="date"
              value={dateRange.end}
              onChange={(e) => {
                setDateRange(prev => ({ ...prev, end: e.target.value }));
                setIsCustomRange(true);
                setActivePreset('');
              }}
              className="px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="bg-blue-50 p-4 rounded-lg">
          <div className="text-sm font-medium text-blue-600">Total SPUs</div>
          <div className="text-2xl font-bold text-blue-900">{rangeData ? rangeData.total_spus.toLocaleString() : '0'}</div>
        </div>
        <div className="bg-green-50 p-4 rounded-lg">
          <div className="text-sm font-medium text-green-600">Average {granularity === 'daily' ? 'Daily' : 'Monthly'}</div>
          <div className="text-2xl font-bold text-green-900">{rangeData ? averageSpus.toFixed(1) : '0'}</div>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-gray-50 p-4 rounded-lg">
        {!rangeData || processedData.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <p>No usage data available for the selected period.</p>
          </div>
        ) : (
          <>
            <div className="flex items-end h-64 gap-2" style={{ justifyContent: processedData.length === 1 ? 'center' : 'space-between' }}>
              {processedData.map((point, index) => {
                const height = maxValue > 0 ? (point.spus / maxValue) * 100 : 0;

                return (
                  <div key={index} className={`flex flex-col items-center ${processedData.length === 1 ? 'w-16' : 'flex-1'} relative`} style={{ height: '100%' }}>
                    <div className="relative w-full flex flex-col justify-end rounded-t overflow-visible" style={{ height: `${height}%`, minHeight: '12px', marginTop: 'auto' }}>
                      {/* Stacked segments — rendered bottom-up, each with its own tooltip */}
                      {[...point.breakdown].reverse().map((seg, si) => {
                        const segHeight = point.spus > 0 ? (seg.spus / point.spus) * 100 : 0;
                        const { bar, label } = operationColor(seg.operation);
                        return (
                          <div
                            key={si}
                            className={`group/seg relative w-full ${bar} transition-all duration-300`}
                            style={{ height: `${segHeight}%` }}
                          >
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover/seg:opacity-100 transition-opacity duration-200 whitespace-nowrap z-20 pointer-events-none">
                              <div className="font-medium">{formatChartDate(point.date)}</div>
                              <div>{label}: {seg.spus.toLocaleString()} SPUs</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* X-axis label */}
                    <div className="text-xs text-gray-600 mt-2 text-center">
                      {formatChartDate(point.date)}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Legend */}
            {(() => {
              const ops = Array.from(new Set(processedData.flatMap(p => p.breakdown.map(b => b.operation)))).sort();
              return ops.length > 1 ? (
                <div className="flex flex-wrap gap-3 mt-3 justify-center">
                  {ops.map(op => {
                    const { bar, label } = operationColor(op);
                    return (
                      <div key={op} className="flex items-center gap-1 text-xs text-gray-600">
                        <div className={`w-3 h-3 rounded-sm ${bar}`} />
                        {label}
                      </div>
                    );
                  })}
                </div>
              ) : null;
            })()}
          </>
        )}
      </div>

    </div>
  );
};

export default SubscriptionSPUUsageChart;
