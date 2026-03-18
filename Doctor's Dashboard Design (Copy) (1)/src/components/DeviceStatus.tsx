import { useEffect, useMemo, useState } from 'react';
import { Wifi, Activity, Check, Watch } from 'lucide-react';

interface DeviceStatusProps {
  patientId?: string;
  useMockData?: boolean;
}

const buildMockStatus = (_seed: number) => {
  return {
    edge_device: {
      status: 'online',
      last_sync: '5 min ago',
    },
    glucose_sensor: {
      status: 'active',
      last_sync: '7 min ago',
    },
    smart_watch: {
      status: 'connected',
      last_sync: '4 min ago',
    },
  };
};

export function DeviceStatus({ patientId, useMockData = false }: DeviceStatusProps) {
  const preloadStatus = (window as any)?.REMONI_PRELOAD?.deviceStatus ?? null;
  const [status, setStatus] = useState<any>(preloadStatus);
  const resolvedPatientId = useMemo(() => {
    return patientId || (window as any)?.REMONI_PATIENT?.id || '00001';
  }, [patientId]);

  useEffect(() => {
    if (useMockData) {
      const seed = Number(resolvedPatientId) || 1;
      const updateMock = () => {
        setStatus(buildMockStatus(seed + Date.now()));
      };
      updateMock();
      const interval = setInterval(updateMock, 30 * 60 * 1000);
      return () => clearInterval(interval);
    }

    const fetchStatus = async () => {
      try {
        const res = await fetch(`/api/device_status?patient_id=${resolvedPatientId}`);
        if (!res.ok) return;
        const data = await res.json();
        setStatus(data);
      } catch (e) {
        console.error('Failed to load device status', e);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [resolvedPatientId, useMockData]);

  const edge = status?.edge_device || {};
  const glucose = status?.glucose_sensor || {};
  const watch = status?.smart_watch || {};

  return (
    <div className="bg-white rounded-lg shadow-md p-2">
      <h3 className="font-bold text-gray-900 mb-2 text-xs">Device Status</h3>
      <div className="grid grid-cols-3 gap-2">
        {/* Edge Device */}
        {[{ name: 'Edge Device', status: edge?.status || 'offline', lastSync: edge?.last_sync || 'Never' }].map((device, index) => {
          const isOnline = device.status === 'online' || device.status === 'connected' || device.status === 'active';
          return (
            <div
              key={index}
              className={`p-1.5 rounded-lg border flex flex-col justify-between ${
                isOnline
                  ? 'border-green-200 bg-green-50'
                  : 'border-red-200 bg-red-50'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1">
                  <Wifi className={`w-3 h-3 ${isOnline ? 'text-green-600' : 'text-red-600'}`} />
                  <p className="font-semibold text-gray-900 text-xs">{device.name}</p>
                </div>
                {isOnline ? (
                  <Check className="w-3 h-3 text-green-600" />
                ) : null}
              </div>
              <p
                className={`text-xs font-medium ${
                  isOnline ? 'text-green-600' : 'text-red-600'
                }`}
              >
                {device.status === 'worn' ? 'Worn' : device.status === 'online' || device.status === 'connected' ? 'Online' : 'Offline'}
              </p>
              <p className="text-xs text-gray-600">Sync: {device.lastSync}</p>
            </div>
          );
        })}

        {/* Glucose Sensor */}
        <div className={`p-1.5 rounded-lg border flex flex-col justify-between ${
          glucose?.status === 'active' || glucose?.status === 'connected'
            ? 'border-green-200 bg-green-50'
            : 'border-red-200 bg-red-50'
        }`}>
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1">
              <Activity className={`w-3 h-3 ${glucose?.status === 'active' || glucose?.status === 'connected' ? 'text-green-600' : 'text-red-600'}`} />
              <p className="font-semibold text-gray-900 text-xs whitespace-nowrap">Glucose Sensor</p>
            </div>
            {(glucose?.status === 'active' || glucose?.status === 'connected') ? (
              <Check className="w-3 h-3 text-green-600" />
            ) : null}
          </div>
          <p className={`text-xs font-medium ${
            glucose?.status === 'active' || glucose?.status === 'connected' ? 'text-green-600' : 'text-red-600'
          }`}>
            {glucose?.status === 'active' || glucose?.status === 'connected' ? 'Active' : 'Offline'}
          </p>
          <p className="text-xs text-gray-600">Sync: {glucose?.last_sync || 'Never'}</p>
        </div>

        {/* Smart Watch */}
        <div className={`p-1.5 rounded-lg border flex flex-col justify-between ${
          watch?.status === 'connected' || watch?.status === 'online'
            ? 'border-green-200 bg-green-50'
            : 'border-red-200 bg-red-50'
        }`}>
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1">
              <Watch className={`w-3 h-3 ${watch?.status === 'connected' || watch?.status === 'online' ? 'text-green-600' : 'text-red-600'}`} />
              <p className="font-semibold text-gray-900 text-xs">Smart Watch</p>
            </div>
            {(watch?.status === 'connected' || watch?.status === 'online') ? (
              <Check className="w-3 h-3 text-green-600" />
            ) : null}
          </div>
          <p className={`text-xs font-medium ${
            watch?.status === 'connected' || watch?.status === 'online' ? 'text-green-600' : 'text-red-600'
          }`}>
            {watch?.status === 'connected' || watch?.status === 'online' ? 'Connected' : 'Offline'}
          </p>
          {(watch?.status === 'connected' || watch?.status === 'online') ? (
            <p className="text-xs text-gray-600">Sync: {watch?.last_sync || 'Never'}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
