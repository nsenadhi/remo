import { Wifi, Activity, Check, X, Network } from 'lucide-react';

export function PatientDeviceStatus() {
  const devices = [
    {
      name: 'Edge Device',
      status: 'online',
      icon: Wifi,
      lastSync: '2 min ago',
      ipAddress: '192.168.1.105',
      wifiSSID: 'HomeNetwork_5G',
    },
    {
      name: 'Glucose Sensor',
      status: 'worn',
      icon: Activity,
      lastSync: '5 min ago',
    },
  ];

  const glucoseSensorActive = true;
  const glucoseSensorLastSync = '5 min ago';

  return (
    <div className="bg-white rounded-lg shadow-md p-3 h-full">
      <div className="grid grid-cols-2 gap-3 h-full">
        {/* Device Status */}
        <div className="flex flex-col">
          <h3 className="font-bold text-gray-900 mb-2 text-xs">Device Status</h3>
          <div className="space-y-2">
            {devices.map((device, index) => {
              const Icon = device.icon;
              const isOnline = device.status === 'online' || device.status === 'worn';
              
              return (
                <div key={index}>
                  <div
                    className={`p-2 rounded-lg border ${
                      isOnline
                        ? 'border-green-200 bg-green-50'
                        : 'border-red-200 bg-red-50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1">
                        <Icon className={`w-3 h-3 ${isOnline ? 'text-green-600' : 'text-red-600'}`} />
                        <p className="font-semibold text-gray-900 text-xs">{device.name}</p>
                      </div>
                      {isOnline ? (
                        <Check className="w-3 h-3 text-green-600" />
                      ) : (
                        <X className="w-3 h-3 text-red-600" />
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
                  
                  {/* Show IP and WiFi for Edge Device */}
                  {device.name === 'Edge Device' && device.ipAddress && (
                    <div className="mt-2 p-2 rounded-lg bg-blue-50 border border-blue-200">
                      <div className="flex items-center gap-1 mb-1">
                        <Network className="w-3 h-3 text-blue-600" />
                        <p className="text-xs font-semibold text-gray-900">Network Info</p>
                      </div>
                      <div className="space-y-0.5">
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600">IP:</span>
                          <span className="text-xs font-medium text-blue-700">{device.ipAddress}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600">WiFi:</span>
                          <span className="text-xs font-medium text-blue-700">{device.wifiSSID}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Glucose Sensor Active Status */}
        <div className="flex flex-col">
          <h3 className="font-bold text-gray-900 mb-2 text-xs">Glucose Sensor</h3>
          <div className="space-y-2">
            <div className={`p-2 rounded-lg border ${
              glucoseSensorActive 
                ? 'border-green-200 bg-green-50' 
                : 'border-red-200 bg-red-50'
            }`}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1">
                  <Activity className={`w-3 h-3 ${glucoseSensorActive ? 'text-green-600' : 'text-red-600'}`} />
                  <p className="font-semibold text-gray-900 text-xs">Status</p>
                </div>
                {glucoseSensorActive ? (
                  <Check className="w-3 h-3 text-green-600" />
                ) : (
                  <X className="w-3 h-3 text-red-600" />
                )}
              </div>
              <p className={`text-xs font-medium ${
                glucoseSensorActive ? 'text-green-600' : 'text-red-600'
              }`}>
                {glucoseSensorActive ? 'Active' : 'Inactive'}
              </p>
              <p className="text-xs text-gray-600">Synced: {glucoseSensorLastSync}</p>
            </div>
            
            {glucoseSensorActive && (
              <div className="p-2 rounded-lg bg-blue-50 border border-blue-200">
                <p className="font-semibold text-gray-900 text-xs mb-1">Battery Level</p>
                <p className="text-xs font-bold text-blue-700 mb-1">78%</p>
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: '78%' }}></div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
