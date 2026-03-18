import { Wifi, Activity, Check, X, Watch } from 'lucide-react';

export function DeviceStatus() {
  const devices = [
    {
      name: 'Edge Device',
      status: 'online',
      icon: Wifi,
      lastSync: '2 min ago',
    },
  ];

  const glucoseSensorActive = true; // true = active, false = inactive
  const glucoseSensorLastSync = '5 min ago';
  
  const watchConnected = true; // true = connected, false = disconnected
  const watchLastSync = '1 min ago';

  return (
    <div className="bg-white rounded-lg shadow-md p-3 h-full">
      <h3 className="font-bold text-gray-900 mb-2 text-xs">Device Status</h3>
      <div className="grid grid-cols-3 gap-2 h-full">
        {/* Edge Device */}
        <div className="flex flex-col">
          <div className="space-y-2">
            {devices.map((device, index) => {
              const Icon = device.icon;
              const isOnline = device.status === 'online' || device.status === 'worn';
              
              return (
                <div
                  key={index}
                  className={`p-2 rounded-lg border ${
                    isOnline
                      ? 'border-green-200 bg-green-50'
                      : 'border-red-200 bg-red-50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-1">
                      <Icon className={`w-3 h-3 flex-shrink-0 ${isOnline ? 'text-green-600' : 'text-red-600'}`} />
                      <p className="font-bold text-gray-900 text-xs whitespace-nowrap">{device.name}</p>
                    </div>
                    {isOnline && (
                      <Check className="w-3 h-3 text-green-600 flex-shrink-0" />
                    )}
                  </div>
                  <p
                    className={`text-xs font-medium ${
                      isOnline ? 'text-green-600' : 'text-red-600'
                    }`}
                  >
                    {device.status === 'worn' ? 'Worn' : device.status === 'online' ? 'Online' : 'Offline'}
                  </p>
                  <p className="text-xs text-gray-600">Sync: {device.lastSync}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Glucose Sensor */}
        <div className="flex flex-col">
          <div className="space-y-2">
            <div className={`p-2 rounded-lg border ${
              glucoseSensorActive 
                ? 'border-green-200 bg-green-50' 
                : 'border-red-200 bg-red-50'
            }`}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1">
                  <Activity className={`w-3 h-3 flex-shrink-0 ${glucoseSensorActive ? 'text-green-600' : 'text-red-600'}`} />
                  <p className="font-bold text-gray-900 text-xs whitespace-nowrap">Glucose Sensor</p>
                </div>
                {glucoseSensorActive && (
                  <Check className="w-3 h-3 text-green-600 flex-shrink-0" />
                )}
              </div>
              <p className={`text-xs font-medium ${
                glucoseSensorActive ? 'text-green-600' : 'text-red-600'
              }`}>
                {glucoseSensorActive ? 'Active' : 'Inactive'}
              </p>
              <p className="text-xs text-gray-600">Synced: {glucoseSensorLastSync}</p>
            </div>
          </div>
        </div>

        {/* Smart Watch */}
        <div className="flex flex-col">
          <div className={`p-2 rounded-lg border ${
            watchConnected 
              ? 'border-green-200 bg-green-50' 
              : 'border-red-200 bg-red-50'
          }`}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-1">
                <Watch className={`w-3 h-3 flex-shrink-0 ${watchConnected ? 'text-green-600' : 'text-red-600'}`} />
                <p className="font-bold text-gray-900 text-xs whitespace-nowrap">Smart Watch</p>
              </div>
              {watchConnected && (
                <Check className="w-3 h-3 text-green-600 flex-shrink-0" />
              )}
            </div>
            <p className={`text-xs font-medium ${
              watchConnected ? 'text-green-600' : 'text-red-600'
            }`}>
              {watchConnected ? 'Connected' : 'Disconnected'}
            </p>
            <p className="text-xs text-gray-600">Sync: {watchLastSync}</p>
          </div>
        </div>
      </div>
    </div>
  );
}