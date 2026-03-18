import { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Heart, Droplet, Activity, Thermometer, Wind, TrendingUp } from 'lucide-react';

// Mock data generators
const generateDailyData = () => {
  return Array.from({ length: 13 }, (_, i) => ({
    time: i * 2,
    heartRate: Math.floor(Math.random() * 30 + 70),
    systolic: Math.floor(Math.random() * 20 + 120),
    diastolic: Math.floor(Math.random() * 15 + 70),
    glucose: Math.floor(Math.random() * 40 + 80),
    temperature: (Math.random() * 2 + 36.5).toFixed(1),
    respiratory: Math.floor(Math.random() * 8 + 12),
    oxygen: Math.floor(Math.random() * 5 + 95),
  }));
};

const generateWeeklyData = () => {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  return days.map((day) => ({
    time: day,
    heartRate: Math.floor(Math.random() * 30 + 70),
    systolic: Math.floor(Math.random() * 20 + 120),
    diastolic: Math.floor(Math.random() * 15 + 70),
    glucose: Math.floor(Math.random() * 40 + 80),
    temperature: (Math.random() * 2 + 36.5).toFixed(1),
    respiratory: Math.floor(Math.random() * 8 + 12),
    oxygen: Math.floor(Math.random() * 5 + 95),
  }));
};

const generateMonthlyData = () => {
  return Array.from({ length: 30 }, (_, i) => ({
    time: `${i + 1}`,
    heartRate: Math.floor(Math.random() * 30 + 70),
    systolic: Math.floor(Math.random() * 20 + 120),
    diastolic: Math.floor(Math.random() * 15 + 70),
    glucose: Math.floor(Math.random() * 40 + 80),
    temperature: (Math.random() * 2 + 36.5).toFixed(1),
    respiratory: Math.floor(Math.random() * 8 + 12),
    oxygen: Math.floor(Math.random() * 5 + 95),
  }));
};

const generateYearlyData = () => {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return months.map((month) => ({
    time: month,
    heartRate: Math.floor(Math.random() * 30 + 70),
    systolic: Math.floor(Math.random() * 20 + 120),
    diastolic: Math.floor(Math.random() * 15 + 70),
    glucose: Math.floor(Math.random() * 40 + 80),
    temperature: (Math.random() * 2 + 36.5).toFixed(1),
    respiratory: Math.floor(Math.random() * 8 + 12),
    oxygen: Math.floor(Math.random() * 5 + 95),
  }));
};

type TimeRange = 'daily' | 'weekly' | 'monthly' | 'yearly';
type ChartType = 'heartRate' | 'bloodPressure' | 'glucose' | 'temperature' | 'respiratory' | 'oxygen';

export function VitalSignsCharts() {
  const [timeRange, setTimeRange] = useState<TimeRange>('daily');
  const [zoomedChart, setZoomedChart] = useState<ChartType | null>(null);

  const getData = () => {
    switch (timeRange) {
      case 'daily':
        return generateDailyData();
      case 'weekly':
        return generateWeeklyData();
      case 'monthly':
        return generateMonthlyData();
      case 'yearly':
        return generateYearlyData();
      default:
        return generateDailyData();
    }
  };

  const data = getData();

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

  return (
    <div className="bg-white rounded-lg shadow-md p-3 h-full flex flex-col overflow-hidden">
      {/* Time Range Selector */}
      <div className="mb-2">
        <h3 className="font-bold text-gray-900 mb-2 text-sm">Vital Signs Monitoring</h3>
        <div className="flex gap-2">
          {(['daily', 'weekly', 'monthly', 'yearly'] as TimeRange[]).map((range) => (
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
                  className="bg-gray-50 rounded-lg p-3 cursor-pointer h-full flex flex-col ring-2 ring-[#9C1DE7]"
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
                        <YAxis tick={{ fontSize: 12 }} stroke="#666" />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#fff',
                            border: '1px solid #ccc',
                            borderRadius: '8px',
                            fontSize: '12px',
                          }}
                        />
                        <Legend wrapperStyle={{ fontSize: '12px' }} />
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
          <div className="flex gap-2 mt-2 flex-wrap">
            {charts.map((chart) => {
              if (chart.id === zoomedChart) return null;
              const Icon = chart.icon;
              
              return (
                <button
                  key={chart.id}
                  onClick={() => handleChartClick(chart.id)}
                  className="bg-gray-100 hover:bg-gray-200 rounded-lg px-3 py-1.5 cursor-pointer transition-all flex items-center gap-1.5"
                >
                  <Icon className="w-3 h-3" style={{ color: chart.color }} />
                  <span className="text-xs font-medium text-gray-700">{chart.title}</span>
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
                className="bg-gray-50 rounded-lg p-2 cursor-pointer transition-all hover:ring-2 hover:ring-[#9C1DE7] flex flex-col"
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
                      <YAxis tick={{ fontSize: 9 }} stroke="#666" />
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