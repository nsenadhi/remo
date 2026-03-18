import { useEffect, useMemo, useState } from 'react';
import { Heart, Activity, Droplet, Thermometer, Wind, TrendingUp } from 'lucide-react';

interface VitalReading {
  name: string;
  value: string;
  unit: string;
  icon: any;
  color: string;
  status: 'normal' | 'high' | 'low';
}

interface LatestVitalsProps {
  patientId?: string;
  showLastReading?: boolean;
}

const THRESHOLDS = {
  heart_rate: { low: 40, high: 130 },
  body_temperature: { low: 27, high: 38 },
  glucose: { low: 70, high: 180 },
  oxygen_saturation: { low: 88, high: 100 },
  systolic_pressure: { low: 90, high: 180 },
  diastolic_pressure: { low: 60, high: 120 },
  respiratory_rate: { low: 10, high: 25 },
};


export function LatestVitals({ patientId, showLastReading = false }: LatestVitalsProps) {
  const preloadVitals = (window as any)?.REMONI_PRELOAD?.latestVitals ?? null;
  const preloadGlucose = (window as any)?.REMONI_PRELOAD?.latestGlucose ?? null;
  const [vitalsData, setVitalsData] = useState<any>(preloadVitals);
  const [glucoseData, setGlucoseData] = useState<any>(preloadGlucose);

  const resolvedPatientId = useMemo(() => {
    return patientId || (window as any)?.REMONI_PATIENT?.id || '00001';
  }, [patientId]);

  useEffect(() => {
    const fetchVitals = async () => {
      try {
        const [vitalsRes, glucoseRes] = await Promise.all([
          fetch(`/api/latest_vitals?patient_id=${resolvedPatientId}`),
          fetch(`/api/latest_glucose?patient_id=${resolvedPatientId}`)
        ]);
        if (vitalsRes.ok) {
          const data = await vitalsRes.json();
          setVitalsData(data);
        }
        if (glucoseRes.ok) {
          const data = await glucoseRes.json();
          setGlucoseData(data);
        }
      } catch (e) {
        console.error('Failed to load latest vitals', e);
      }
    };
    fetchVitals();
    const interval = setInterval(fetchVitals, 10000);
    return () => clearInterval(interval);
  }, [resolvedPatientId]);

  const heartRate = Number(vitalsData?.heart_rate ?? 0);
  const systolic = Number(vitalsData?.blood_pressure?.systolic ?? 0);
  const diastolic = Number(vitalsData?.blood_pressure?.diastolic ?? 0);
  const glucose = Number(glucoseData?.value_mgdl ?? 0);
  const temperature = Number(vitalsData?.skin_temperature ?? 0);
  const respiratory = Number(vitalsData?.respiratory_rate ?? 0);
  const oxygen = Number(vitalsData?.spo2 ?? 0);
  const lastReadingRaw = vitalsData?.datetime && vitalsData?.datetime !== 'Never' ? vitalsData.datetime : null;

  const formatTime = (value: string) => {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  const minutesAgo = (value: string) => {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return '';
    const deltaMinutes = Math.max(0, Math.round((Date.now() - parsed.getTime()) / 60000));
    return `${deltaMinutes} min ago`;
  };

  const vitals: VitalReading[] = [
    {
      name: 'Heart Rate',
      value: String(heartRate || 0),
      unit: 'BPM',
      icon: Heart,
      color: '#ef4444',
      status:
        heartRate > THRESHOLDS.heart_rate.high ? 'high'
        : heartRate < THRESHOLDS.heart_rate.low ? 'low'
        : 'normal',
    },
    {
      name: 'Blood Pressure',
      value: `${systolic || 0}/${diastolic || 0}`,
      unit: 'mmHg',
      icon: Activity,
      color: '#9C1DE7',
      status:
        systolic > THRESHOLDS.systolic_pressure.high || diastolic > THRESHOLDS.diastolic_pressure.high
          ? 'high'
          : systolic < THRESHOLDS.systolic_pressure.low || diastolic < THRESHOLDS.diastolic_pressure.low
          ? 'low'
          : 'normal',
    },
    {
      name: 'Blood Glucose',
      value: String(glucose || 0),
      unit: 'mg/dL',
      icon: Droplet,
      color: '#3b82f6',
      status:
        glucose > THRESHOLDS.glucose.high ? 'high'
        : glucose < THRESHOLDS.glucose.low ? 'low'
        : 'normal',
    },
    {
      name: 'Body Temperature',
      value: temperature ? temperature.toFixed(1) : '0',
      unit: '°C',
      icon: Thermometer,
      color: '#f97316',
      status:
        temperature > THRESHOLDS.body_temperature.high ? 'high'
        : temperature < THRESHOLDS.body_temperature.low ? 'low'
        : 'normal',
    },
    {
      name: 'Respiratory Rate',
      value: String(respiratory || 0),
      unit: 'breaths/min',
      icon: Wind,
      color: '#10b981',
      status:
        respiratory > THRESHOLDS.respiratory_rate.high ? 'high'
        : respiratory < THRESHOLDS.respiratory_rate.low ? 'low'
        : 'normal',
    },
    {
      name: 'Blood Oxygen',
      value: String(oxygen || 0),
      unit: '%',
      icon: TrendingUp,
      color: '#06b6d4',
      status:
        oxygen > THRESHOLDS.oxygen_saturation.high ? 'high'
        : oxygen < THRESHOLDS.oxygen_saturation.low ? 'low'
        : 'normal',
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
    <div>
      {showLastReading && (
        <p className="text-xs text-gray-500 mb-2">
          {lastReadingRaw
            ? `Last reading at ${formatTime(lastReadingRaw)} (${minutesAgo(lastReadingRaw)})`
            : 'Last reading: Never'}
        </p>
      )}
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
