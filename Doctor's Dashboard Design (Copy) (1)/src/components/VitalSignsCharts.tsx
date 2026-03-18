import { useEffect, useMemo, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from 'recharts';
import { Heart, Droplet, Activity, Thermometer, Wind, TrendingUp } from 'lucide-react';

type TimeRange = 'daily' | 'weekly' | 'monthly';
type ChartType = 'heartRate' | 'bloodPressure' | 'glucose' | 'temperature' | 'respiratory' | 'oxygen';

const ThresholdLabel = (props: any) => {
  const { viewBox, value, fill } = props || {};
  if (!viewBox || value == null) return null;
  const text = String(value);
  const paddingX = 4;
  const paddingY = 2;
  const width = text.length * 6 + paddingX * 2;
  const height = 12 + paddingY * 2;
  const x = (viewBox.x || 0) + 6;
  const y = (viewBox.y || 0) - 6;

  return (
    <g>
      <rect
        x={x}
        y={y - height + 4}
        width={width}
        height={height}
        fill="#ffffff"
        opacity={0.9}
        rx={3}
      />
      <text x={x + paddingX} y={y} fill={fill || '#111827'} fontSize={10} fontWeight={600}>
        {text}
      </text>
    </g>
  );
};

const THRESHOLDS = {
  heartRate: { low: 40, high: 130 },
  bloodPressure: { sysLow: 90, sysHigh: 180, diaLow: 60, diaHigh: 120 },
  glucose: { low: 70, high: 180 },
  temperature: { low: 27, high: 38 },
  respiratory: { low: 10, high: 25 },
  oxygen: { low: 88, high: 100 },
};

interface VitalSignsChartsProps {
  patientId?: string;
  useMockData?: boolean;
}

const buildMockSeries = (seed: number, range: TimeRange) => {
  const rand = (offset: number, mod: number) => (seed * (offset + 11) * 9301 + 49297) % 233280 % mod;
  const base = (index: number) => ({
    heartRate: 70 + (rand(index, 20) % 20),
    systolic: 110 + (rand(index + 1, 16) % 16),
    diastolic: 70 + (rand(index + 2, 12) % 12),
    glucose: 90 + (rand(index + 3, 50) % 50),
    temperature: 36.5 + ((rand(index + 4, 7) % 7) / 10),
    respiratory: 12 + (rand(index + 5, 7) % 7),
    oxygen: 96 + (rand(index + 6, 4) % 4),
  });

  if (range === 'daily') {
    return Array.from({ length: 12 }, (_, i) => ({
      time: `${(i + 1) * 2}:00`,
      ...base(i),
    }));
  }
  if (range === 'weekly') {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    return days.map((day, i) => ({ time: day, ...base(i) }));
  }
  if (range === 'monthly') {
    return Array.from({ length: 30 }, (_, i) => ({
      time: String(i + 1),
      ...base(i),
    }));
  }
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return months.map((month, i) => ({ time: month, ...base(i) }));
};

export function VitalSignsCharts({ patientId, useMockData = false }: VitalSignsChartsProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>('daily');
  const [zoomedChart, setZoomedChart] = useState<ChartType | null>(null);
  const preloadSeries = (window as any)?.REMONI_PRELOAD?.vitalsSeries?.daily ?? [];
  const [data, setData] = useState<any[]>(preloadSeries);

  const resolvedPatientId = useMemo(() => {
    return patientId || (window as any)?.REMONI_PATIENT?.id || '00001';
  }, [patientId]);

  useEffect(() => {
    if (useMockData) {
      setData(buildMockSeries(Number(resolvedPatientId) || 1, timeRange));
      return;
    }

    const fetchSeries = async () => {
      try {
        const res = await fetch(`/api/vitals_series?patient_id=${resolvedPatientId}&period=${timeRange}`);
        if (!res.ok) return;
        const payload = await res.json();
        const series = Array.isArray(payload?.series) ? payload.series : [];
        setData(series);
      } catch (e) {
        console.error('Failed to load vitals series', e);
      }
    };
    fetchSeries();
  }, [resolvedPatientId, timeRange, useMockData]);

  const charts = [
    {
      id: 'heartRate' as ChartType,
      title: 'Heart Rate',
      unit: 'BPM',
      icon: Heart,
      color: '#ef4444',
      dataKey: 'heartRate',
    },
    {
      id: 'bloodPressure' as ChartType,
      title: 'Blood Pressure',
      unit: 'mmHg',
      icon: Activity,
      color: '#9C1DE7',
      dataKeys: ['systolic', 'diastolic'],
    },
    {
      id: 'glucose' as ChartType,
      title: 'Glucose',
      unit: 'mg/dL',
      icon: Droplet,
      color: '#3b82f6',
      dataKey: 'glucose',
    },
    {
      id: 'temperature' as ChartType,
      title: 'Temperature',
      unit: '°C',
      icon: Thermometer,
      color: '#f97316',
      dataKey: 'temperature',
    },
    {
      id: 'respiratory' as ChartType,
      title: 'Respiratory',
      unit: 'br/min',
      icon: Wind,
      color: '#10b981',
      dataKey: 'respiratory',
    },
    {
      id: 'oxygen' as ChartType,
      title: 'Oxygen',
      unit: '%',
      icon: TrendingUp,
      color: '#06b6d4',
      dataKey: 'oxygen',
    },
  ];

  const handleChartClick = (chartId: ChartType) => {
    setZoomedChart(zoomedChart === chartId ? null : chartId);
  };

  const renderThresholdLines = (chartId: ChartType) => {
    switch (chartId) {
      case 'heartRate':
        return (
          <>
            <ReferenceLine y={THRESHOLDS.heartRate.high} stroke="#ef4444" strokeDasharray="4 4" />
            <ReferenceLine y={THRESHOLDS.heartRate.low} stroke="#f59e0b" strokeDasharray="4 4" />
          </>
        );
      case 'bloodPressure':
        return (
          <>
            <ReferenceLine
              y={THRESHOLDS.bloodPressure.sysHigh}
              stroke="#ef4444"
              strokeDasharray="4 4"
              label={<ThresholdLabel value="Sys High" fill="#ef4444" />}
            />
            <ReferenceLine
              y={THRESHOLDS.bloodPressure.sysLow}
              stroke="#ef4444"
              strokeDasharray="4 4"
              label={<ThresholdLabel value="Sys Low" fill="#ef4444" />}
            />
            <ReferenceLine
              y={THRESHOLDS.bloodPressure.diaHigh}
              stroke="#9C1DE7"
              strokeDasharray="4 4"
              label={<ThresholdLabel value="Dia High" fill="#9C1DE7" />}
            />
            <ReferenceLine
              y={THRESHOLDS.bloodPressure.diaLow}
              stroke="#9C1DE7"
              strokeDasharray="4 4"
              label={<ThresholdLabel value="Dia Low" fill="#9C1DE7" />}
            />
          </>
        );
      case 'glucose':
        return (
          <>
            <ReferenceLine y={THRESHOLDS.glucose.high} stroke="#ef4444" strokeDasharray="4 4" />
            <ReferenceLine y={THRESHOLDS.glucose.low} stroke="#f59e0b" strokeDasharray="4 4" />
          </>
        );
      case 'temperature':
        return (
          <>
            <ReferenceLine y={THRESHOLDS.temperature.high} stroke="#ef4444" strokeDasharray="4 4" />
            <ReferenceLine y={THRESHOLDS.temperature.low} stroke="#f59e0b" strokeDasharray="4 4" />
          </>
        );
      case 'respiratory':
        return (
          <>
            <ReferenceLine y={THRESHOLDS.respiratory.high} stroke="#ef4444" strokeDasharray="4 4" />
            <ReferenceLine y={THRESHOLDS.respiratory.low} stroke="#f59e0b" strokeDasharray="4 4" />
          </>
        );
      case 'oxygen':
        return (
          <>
            <ReferenceLine y={THRESHOLDS.oxygen.low} stroke="#f59e0b" strokeDasharray="4 4" />
          </>
        );
      default:
        return null;
    }
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Time Range Selector */}
      <div className="mb-2">
        <h3 className="font-bold text-gray-900 mb-2 text-sm">Vital Signs Monitoring</h3>
        <div className="flex gap-2">
          {(['daily', 'weekly', 'monthly'] as TimeRange[]).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1 rounded-lg font-medium transition-colors text-xs ${
                timeRange === range
                  ? 'bg-[#581B98] text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {range.charAt(0).toUpperCase() + range.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Charts Display */}
      {zoomedChart ? (
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {/* Zoomed Chart */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {charts.map((chart) => {
              if (chart.id !== zoomedChart) return null;
              const Icon = chart.icon;

              return (
                <div
                  key={chart.id}
                  onClick={() => handleChartClick(chart.id)}
                  className="bg-gray-50 rounded-lg p-3 cursor-pointer h-full flex flex-col"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Icon className="w-4 h-4" style={{ color: chart.color }} />
                      <h4 className="font-semibold text-gray-900 text-sm">{chart.title}</h4>
                    </div>
                    <span className="text-xs text-gray-600">{chart.unit}</span>
                  </div>

                  <div className="flex-1 min-h-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                        <XAxis dataKey="time" tick={{ fontSize: 12 }} stroke="#666" />
                        <YAxis
                          tick={{ fontSize: 12 }}
                          stroke="#666"
                          domain={
                            chart.id === 'temperature'
                              ? [20, 40]
                              : chart.id === 'oxygen'
                                ? [80, 100]
                                : undefined
                          }
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#fff',
                            border: '1px solid #ccc',
                            borderRadius: '8px',
                            fontSize: '12px',
                          }}
                        />
                        {chart.id === 'bloodPressure' && <Legend wrapperStyle={{ fontSize: '12px' }} />}
                        {renderThresholdLines(chart.id)}
                        {chart.dataKeys ? (
                          <>
                            <Line
                              type="monotone"
                              dataKey={chart.dataKeys[0]}
                              stroke={chart.color}
                              strokeWidth={3}
                              dot={true}
                              name="Systolic"
                            />
                            <Line
                              type="monotone"
                              dataKey={chart.dataKeys[1]}
                              stroke="#581B98"
                              strokeWidth={3}
                              dot={true}
                              name="Diastolic"
                            />
                          </>
                        ) : (
                          <Line
                            type="monotone"
                            dataKey={chart.dataKey}
                            stroke={chart.color}
                            strokeWidth={3}
                            dot={true}
                          />
                        )}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Minimized Charts Row */}
          <div className="flex gap-2 mt-2 flex-wrap items-center">
            <button
              type="button"
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setZoomedChart(null);
              }}
              className="bg-gray-100 hover:bg-gray-200 rounded-lg px-3 py-1.5 cursor-pointer transition-all text-xs font-medium text-gray-700"
            >
              Previous
            </button>
            {charts.map((chart) => {
              const Icon = chart.icon;
              const isActive = chart.id === zoomedChart;
              
              return (
                <button
                  key={chart.id}
                  onClick={() => handleChartClick(chart.id)}
                  className={`rounded-lg px-3 py-1.5 cursor-pointer transition-all flex items-center gap-1.5 ${
                    isActive ? 'bg-[#581B98] text-white' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                  }`}
                >
                  <Icon className="w-3 h-3" style={{ color: isActive ? '#ffffff' : chart.color }} />
                  <span className={`text-xs font-medium ${isActive ? 'text-white' : 'text-gray-700'}`}>{chart.title}</span>
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        /* Grid View - All Charts */
        <div className="flex-1 grid grid-cols-3 gap-3 min-h-0">
          {charts.map((chart) => {
            const Icon = chart.icon;

            return (
              <div
                key={chart.id}
                onClick={() => handleChartClick(chart.id)}
                className="bg-gray-50 rounded-lg p-2 cursor-pointer transition-all flex flex-col"
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <Icon className="w-3.5 h-3.5" style={{ color: chart.color }} />
                    <h4 className="font-semibold text-gray-900 text-xs">{chart.title}</h4>
                  </div>
                  <span className="text-xs text-gray-600">{chart.unit}</span>
                </div>

                <div className="flex-1 min-h-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                      <XAxis dataKey="time" tick={{ fontSize: 9 }} stroke="#666" />
                      <YAxis
                        tick={{ fontSize: 9 }}
                        stroke="#666"
                        domain={
                          chart.id === 'temperature'
                            ? [20, 40]
                            : chart.id === 'oxygen'
                              ? [80, 100]
                              : undefined
                        }
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#fff',
                          border: '1px solid #ccc',
                          borderRadius: '8px',
                          fontSize: '11px',
                        }}
                      />
                      {chart.dataKeys ? (
                        <>
                          <Line
                            type="monotone"
                            dataKey={chart.dataKeys[0]}
                            stroke={chart.color}
                            strokeWidth={2}
                            dot={false}
                            name="Systolic"
                          />
                          <Line
                            type="monotone"
                            dataKey={chart.dataKeys[1]}
                            stroke="#581B98"
                            strokeWidth={2}
                            dot={false}
                            name="Diastolic"
                          />
                        </>
                      ) : (
                        <Line
                          type="monotone"
                          dataKey={chart.dataKey}
                          stroke={chart.color}
                          strokeWidth={2}
                          dot={false}
                        />
                      )}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
