import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import { Moon, Watch } from 'lucide-react';

// Mock data for the last 7 days - showing time ranges
const generateActivityData = () => {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  return days.map((day) => {
    // Sleep: e.g., 22:00 to 6:00 (crosses midnight)
    const sleepStart = Math.floor(Math.random() * 2 + 22); // 22-23
    const sleepEnd = Math.floor(Math.random() * 2 + 6); // 6-7
    const sleepDuration = sleepEnd + (24 - sleepStart); // Duration accounting for midnight crossing
    
    // Watch worn: e.g., 7:00 to 21:00
    const wornStart = Math.floor(Math.random() * 2 + 8); // 8-9
    const wornEnd = Math.floor(Math.random() * 3 + 19); // 19-21
    const wornDuration = wornEnd - wornStart;
    
    return {
      day,
      sleepStart,
      sleepEnd,
      sleepDuration,
      sleepOffset: sleepStart, // Where the sleep bar starts on the Y axis
      wornStart,
      wornEnd,
      wornDuration,
      wornOffset: wornStart, // Where the worn bar starts on the Y axis
      sleepRange: `${sleepStart}:00-${sleepEnd}:00`,
      wornRange: `${wornStart}:00-${wornEnd}:00`,
    };
  });
};

export function ActivityMonitor() {
  const data = generateActivityData();
  
  // Calculate averages
  const avgSleepStart = Math.round(data.reduce((sum, d) => sum + d.sleepStart, 0) / data.length);
  const avgSleepEnd = Math.round(data.reduce((sum, d) => sum + d.sleepEnd, 0) / data.length);
  const avgSleepDuration = ((avgSleepEnd + (24 - avgSleepStart))).toFixed(1);
  
  const avgWornStart = Math.round(data.reduce((sum, d) => sum + d.wornStart, 0) / data.length);
  const avgWornEnd = Math.round(data.reduce((sum, d) => sum + d.wornEnd, 0) / data.length);
  const avgWornDuration = ((avgWornEnd - avgWornStart)).toFixed(1);

  return (
    <div className="bg-white rounded-lg shadow-md p-3 h-full flex flex-col min-h-0">
      <h3 className="font-bold text-gray-900 mb-2 text-sm">Activity Monitor</h3>
      
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={4}>
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
            <Tooltip 
              contentStyle={{ 
                backgroundColor: '#fff', 
                border: '1px solid #ccc',
                borderRadius: '8px',
                fontSize: '11px'
              }}
              formatter={(value: any, name: any, props: any) => {
                const item = props.payload;
                if (name === 'Sleep Time') {
                  return [`${item.sleepStart}:00 - ${item.sleepEnd}:00 (${item.sleepDuration}h)`, 'Sleep Time'];
                } else if (name === 'Watch Worn') {
                  return [`${item.wornStart}:00 - ${item.wornEnd}:00 (${item.wornDuration}h)`, 'Watch Worn'];
                }
                return [value, name];
              }}
            />
            <Legend 
              wrapperStyle={{ fontSize: '11px' }}
              iconType="circle"
            />
            {/* Sleep bars - offset then duration */}
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
            {/* Watch worn bars - offset then duration */}
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