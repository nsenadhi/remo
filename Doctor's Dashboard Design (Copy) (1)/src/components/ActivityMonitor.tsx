import { useEffect, useMemo, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend, ResponsiveContainer } from 'recharts';
import { Moon, Watch } from 'lucide-react';

interface ActivityMonitorProps {
  patientId?: string;
  useMockData?: boolean;
}

const generateMockActivityData = (seed: number) => {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  return days.map((day, index) => {
    const base = seed + index * 17;
    const sleepStart = 22 + (base % 2);
    const sleepEnd = 6 + ((base + 1) % 2);
    const sleepDuration = sleepEnd + (24 - sleepStart);
    const wornStart = 8 + (base % 2);
    const wornEnd = 19 + ((base + 2) % 3);
    const wornDuration = wornEnd - wornStart;
    return {
      day,
      sleepStart,
      sleepEnd,
      sleepDuration,
      sleepOffset: sleepStart,
      wornStart,
      wornEnd,
      wornDuration,
      wornOffset: wornStart,
      sleepRange: `${sleepStart}:00-${sleepEnd}:00`,
      wornRange: `${wornStart}:00-${wornEnd}:00`,
    };
  });
};

export function ActivityMonitor({ patientId, useMockData = false }: ActivityMonitorProps) {
  const preloadUsage = (window as any)?.REMONI_PRELOAD?.dailyUsage ?? [];
  const [data, setData] = useState<any[]>(preloadUsage);

  const resolvedPatientId = useMemo(() => {
    return patientId || (window as any)?.REMONI_PATIENT?.id || '00001';
  }, [patientId]);

  useEffect(() => {
    if (useMockData) {
      setData(generateMockActivityData(Number(resolvedPatientId) || 1));
      return;
    }

    const fetchUsage = async () => {
      try {
        const res = await fetch(`/api/daily_usage?patient_id=${resolvedPatientId}&days=7`);
        if (!res.ok) return;
        const payload = await res.json();
        const rows = Array.isArray(payload?.data) ? payload.data : [];
        setData(rows);
      } catch (e) {
        console.error('Failed to load daily usage', e);
      }
    };
    fetchUsage();
  }, [resolvedPatientId, useMockData]);

  const mapped = data.map((row: any) => {
    const sleepStart = row.sleepStart ?? row.sleep_start ?? row.sleepOffset ?? 0;
    const sleepEnd = row.sleepEnd ?? row.sleep_end ?? 0;
    const watchStart = row.watchStart ?? row.wornStart ?? row.watchOffset ?? 0;
    const watchEnd = row.watchEnd ?? row.wornEnd ?? 0;
    return {
      day: row.day || row.date || '',
      sleepStart,
      sleepEnd,
      sleepDuration: row.sleepDuration ?? row.sleep_duration ?? 0,
      sleepOffset: row.sleepOffset ?? sleepStart ?? 0,
      wornStart: watchStart,
      wornEnd: watchEnd,
      wornDuration: row.watchDuration ?? row.watch_duration ?? 0,
      wornOffset: row.watchOffset ?? watchStart ?? 0,
      sleepRange: row.sleepLabel || `${sleepStart}:00-${sleepEnd}:00`,
      wornRange: row.watchLabel || `${watchStart}:00-${watchEnd}:00`,
    };
  });

  const avgSleepStart = mapped.length ? Math.round(mapped.reduce((sum, d) => sum + (d.sleepStart || 0), 0) / mapped.length) : 0;
  const avgSleepEnd = mapped.length ? Math.round(mapped.reduce((sum, d) => sum + (d.sleepEnd || 0), 0) / mapped.length) : 0;
  const avgSleepDuration = mapped.length ? ((avgSleepEnd + (24 - avgSleepStart))).toFixed(1) : '0.0';
  
  const avgWornStart = mapped.length ? Math.round(mapped.reduce((sum, d) => sum + (d.wornStart || 0), 0) / mapped.length) : 0;
  const avgWornEnd = mapped.length ? Math.round(mapped.reduce((sum, d) => sum + (d.wornEnd || 0), 0) / mapped.length) : 0;
  const avgWornDuration = mapped.length ? ((avgWornEnd - avgWornStart)).toFixed(1) : '0.0';

  return (
    <div className="bg-white rounded-lg shadow-md p-3 h-full flex flex-col min-h-0">
      <h3 className="font-bold text-gray-900 mb-2 text-sm">Activity Monitor</h3>
      
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={mapped} barGap={4}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
            <XAxis 
              dataKey="day" 
              tick={{ fontSize: 11 }} 
              stroke="#666"
            />
            <YAxis 
              tick={{ fontSize: 11 }} 
              stroke="#666"
              domain={[0, 24]}
              ticks={[0, 6, 12, 18, 24]}
              label={{ value: 'Time (24h)', angle: -90, position: 'insideLeft', fontSize: 11 }}
            />
            <Legend 
              wrapperStyle={{ fontSize: '11px' }}
              iconType="circle"
            />
            <Bar 
              dataKey="sleepOffset" 
              stackId="sleep"
              fill="transparent" 
              name=""
              legendType="none"
            />
            <Bar 
              dataKey="sleepDuration" 
              stackId="sleep"
              fill="#9C1DE7" 
              name="Sleep Time"
              radius={[4, 4, 4, 4]}
            />
            <Bar 
              dataKey="wornOffset" 
              stackId="worn"
              fill="transparent" 
              name=""
              legendType="none"
            />
            <Bar 
              dataKey="wornDuration" 
              stackId="worn"
              fill="#06b6d4" 
              name="Watch Worn"
              radius={[4, 4, 4, 4]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-2 gap-2 mt-2">
        <div className="flex items-start gap-2 bg-purple-50 p-2 rounded-lg border border-purple-200">
          <Moon className="w-4 h-4 text-[#9C1DE7] mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-gray-900">Sleep Time</p>
            <p className="text-sm font-bold text-[#9C1DE7]">{avgSleepStart}:00 - {avgSleepEnd}:00</p>
            <p className="text-xs text-gray-600">Avg: {avgSleepDuration}h</p>
          </div>
        </div>
        <div className="flex items-start gap-2 bg-cyan-50 p-2 rounded-lg border border-cyan-200">
          <Watch className="w-4 h-4 text-cyan-600 mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-gray-900">Watch Worn</p>
            <p className="text-sm font-bold text-cyan-600">{avgWornStart}:00 - {avgWornEnd}:00</p>
            <p className="text-xs text-gray-600">Avg: {avgWornDuration}h</p>
          </div>
        </div>
      </div>
    </div>
  );
}
