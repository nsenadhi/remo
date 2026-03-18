import { useEffect, useState } from 'react';
import { Chatroom } from './components/Chatroom';

export default function App() {
  const [role, setRole] = useState<'doctor' | 'patient'>('doctor');

  useEffect(() => {
    const loadSession = async () => {
      try {
        const res = await fetch('/api/chatroom/session');
        const data = await res.json();
        if (data && data.role) {
          setRole(data.role);
        }
      } catch {
        // ignore
      }
    };
    loadSession();
  }, []);

  return (
    <Chatroom />
  );
}
