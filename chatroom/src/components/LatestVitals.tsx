import { Heart, Activity, Droplet, Thermometer, Wind, TrendingUp } from 'lucide-react';

interface VitalReading {
  name: string;
  value: string;
  unit: string;
  icon: any;
  color: string;
  status: 'normal' | 'high' | 'low';
}

export function LatestVitals() {
  const vitals: VitalReading[] = [
    {
      name: 'Heart Rate',
      value: '72',
      unit: 'BPM',
      icon: Heart,
      color: '#ef4444',
      status: 'normal',
    },
    {
      name: 'Blood Pressure',
      value: '140/90',
      unit: 'mmHg',
      icon: Activity,
      color: '#9C1DE7',
      status: 'high',
    },
    {
      name: 'Blood Glucose',
      value: '98',
      unit: 'mg/dL',
      icon: Droplet,
      color: '#3b82f6',
      status: 'normal',
    },
    {
      name: 'Body Temperature',
      value: '36.8',
      unit: '°C',
      icon: Thermometer,
      color: '#f97316',
      status: 'normal',
    },
    {
      name: 'Respiratory Rate',
      value: '16',
      unit: 'breaths/min',
      icon: Wind,
      color: '#10b981',
      status: 'normal',
    },
    {
      name: 'Blood Oxygen',
      value: '98',
      unit: '%',
      icon: TrendingUp,
      color: '#06b6d4',
      status: 'normal',
    },
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'high':
        return 'bg-red-100 border-red-300';
      case 'low':
        return 'bg-yellow-100 border-yellow-300';
      case 'normal':
        return 'bg-green-50 border-green-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const getTextColor = (status: string) => {
    switch (status) {
      case 'high':
        return 'text-red-700';
      case 'low':
        return 'text-yellow-700';
      case 'normal':
        return 'text-green-700';
      default:
        return 'text-gray-700';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-2 h-full">
      <p className="text-xs text-gray-500 mb-1">Last reading at 2:00 PM (10 min ago)</p>
      <div className="grid grid-cols-3 md:grid-cols-6 gap-1.5">
        {vitals.map((vital, index) => {
          const Icon = vital.icon;
          return (
            <div
              key={index}
              className={`rounded-lg p-1.5 border ${getStatusColor(vital.status)}`}
            >
              <div className="flex items-center gap-1 mb-0.5">
                <Icon className="w-2.5 h-2.5" style={{ color: vital.color }} />
                <p className="text-xs text-gray-600 leading-tight truncate">{vital.name}</p>
              </div>
              <div className="flex items-baseline gap-0.5">
                <p className={`text-base font-bold ${getTextColor(vital.status)}`}>
                  {vital.value}
                </p>
              </div>
              <p className="text-xs text-gray-500 truncate">{vital.unit}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}