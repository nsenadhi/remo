import { useState, useRef, useEffect } from 'react';
import { Send, UserCircle, Stethoscope, Bot, X, ArrowLeft, LogOut, Reply } from 'lucide-react';

interface Message {
  id: number;
  sender: 'doctor' | 'patient' | 'remoni';
  text: string;
  timestamp: string;
  date: string;
  senderName: string;
  replyTo?: {
    id: number;
    senderName: string;
    text: string;
  };
}

interface ChatroomProps {
  onBack: () => void;
  onLogout: () => void;
}

export function Chatroom({ onBack, onLogout }: ChatroomProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      sender: 'remoni',
      text: 'Hello! I\'m REMONI, your virtual health assistant. I\'m here to help monitor your health and facilitate communication.',
      timestamp: '09:00 AM',
      date: '2026-01-05',
      senderName: 'REMONI AI',
    },
    {
      id: 2,
      sender: 'doctor',
      text: 'Good morning! How are you feeling today?',
      timestamp: '09:15 AM',
      date: '2026-01-05',
      senderName: 'Dr. Smith',
    },
    {
      id: 3,
      sender: 'patient',
      text: 'Good morning, Doctor. I\'m feeling much better, thank you!',
      timestamp: '09:18 AM',
      date: '2026-01-05',
      senderName: 'Patient Name',
    },
    {
      id: 4,
      sender: 'remoni',
      text: 'Patient\'s vital signs are stable. Blood pressure: 120/80, Heart rate: 72 bpm, Temperature: 98.6°F',
      timestamp: '09:20 AM',
      date: '2026-01-05',
      senderName: 'REMONI AI',
    },
  ]);

  const [newMessage, setNewMessage] = useState('');
  const [currentUser, setCurrentUser] = useState<'doctor' | 'patient' | 'remoni'>('doctor');
  const [replyingTo, setReplyingTo] = useState<Message | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = () => {
    if (newMessage.trim() === '') return;

    const senderNames = {
      doctor: 'Dr. Smith',
      patient: 'Patient Name',
      remoni: 'REMONI AI',
    };

    const now = new Date();
    const timestamp = now.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: true 
    });
    const date = now.toISOString().split('T')[0];

    const message: Message = {
      id: messages.length + 1,
      sender: currentUser,
      text: newMessage,
      timestamp: timestamp,
      date: date,
      senderName: senderNames[currentUser],
      replyTo: replyingTo ? { id: replyingTo.id, senderName: replyingTo.senderName, text: replyingTo.text } : undefined,
    };

    setMessages([...messages, message]);
    setNewMessage('');
    setReplyingTo(null);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const getMessageStyle = (sender: 'doctor' | 'patient' | 'remoni') => {
    switch (sender) {
      case 'doctor':
        return {
          bg: 'bg-gradient-to-r from-[#581B98] to-[#9C1DE7]',
          text: 'text-white',
          icon: Stethoscope,
          iconColor: 'text-white',
          align: 'justify-start',
        };
      case 'patient':
        return {
          bg: 'bg-gray-200',
          text: 'text-gray-900',
          icon: UserCircle,
          iconColor: 'text-gray-700',
          align: 'justify-end',
        };
      case 'remoni':
        return {
          bg: 'bg-blue-500',
          text: 'text-white',
          icon: Bot,
          iconColor: 'text-white',
          align: 'justify-start',
        };
    }
  };

  const shouldShowDateSeparator = (currentMessage: Message, previousMessage: Message | null) => {
    if (!previousMessage) return true;
    return currentMessage.date !== previousMessage.date;
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    const dateOnly = dateStr;
    const todayStr = today.toISOString().split('T')[0];
    const yesterdayStr = yesterday.toISOString().split('T')[0];

    if (dateOnly === todayStr) return 'Today';
    if (dateOnly === yesterdayStr) return 'Yesterday';
    
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const formatMessageDateTime = (dateStr: string, timeStr: string) => {
    const date = new Date(dateStr);
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${month}/${day} ${timeStr}`;
  };

  return (
    <div className="h-screen w-screen bg-white flex flex-col overflow-hidden">
      {/* Header */}
      <header className="bg-gradient-to-r from-[#581B98] to-[#9C1DE7] text-white shadow-md flex-shrink-0">
        <div className="px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">REMONI Chatroom</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="flex items-center gap-2 bg-white/20 hover:bg-white/30 text-white px-4 py-2 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Dashboard</span>
            </button>
            <button
              onClick={onLogout}
              className="flex items-center gap-2 bg-white/20 hover:bg-white/30 text-white px-4 py-2 rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 w-full flex flex-col overflow-hidden bg-white">
        <div className="h-full flex flex-col overflow-hidden">
          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {messages.map((message, index) => {
              const style = getMessageStyle(message.sender);
              const Icon = style.icon;
              const isOwnMessage = message.sender === 'patient';
              const previousMessage = index > 0 ? messages[index - 1] : null;
              const showDateSeparator = shouldShowDateSeparator(message, previousMessage);

              return (
                <div key={message.id}>
                  {/* Date Separator */}
                  {showDateSeparator && (
                    <div className="flex justify-center my-4">
                      <div className="bg-gray-200 text-gray-600 text-xs font-semibold px-4 py-1 rounded-full">
                        {formatDate(message.date)}
                      </div>
                    </div>
                  )}
                  
                  <div className={`flex ${style.align}`}>
                    <div className={`max-w-[70%] ${isOwnMessage ? 'order-2' : 'order-1'}`}>
                      {/* Name and timestamp above message */}
                      <div className={`flex items-center gap-2 mb-1 ${isOwnMessage ? 'justify-end' : 'justify-start'}`}>
                        <span className={`text-xs font-bold ${
                          message.sender === 'remoni' ? 'text-blue-600' : 
                          message.sender === 'doctor' ? 'text-[#581B98]' : 
                          'text-gray-700'
                        }`}>
                          {message.senderName}
                        </span>
                        <span className="text-xs text-gray-500">{formatMessageDateTime(message.date, message.timestamp)}</span>
                      </div>
                      
                      {/* Icon and message bubble in line */}
                      <div className="flex items-start gap-2 group">
                        {/* Show icon only for other users (not current user) */}
                        {!isOwnMessage && (
                          <div className={`${style.bg} p-2 rounded-full flex-shrink-0`}>
                            <Icon className={`w-5 h-5 ${style.iconColor}`} />
                          </div>
                        )}
                        
                        <div 
                          className={`${style.bg} ${style.text} p-3 rounded-lg shadow-sm cursor-pointer hover:opacity-90 transition-opacity flex-1`}
                          onClick={() => setReplyingTo(message)}
                        >
                          {/* Show replied message if exists */}
                          {message.replyTo && (
                            <div className="mb-2 pb-2 border-l-2 border-white/30 pl-2 opacity-80">
                              <div className="text-xs font-semibold">{message.replyTo.senderName}</div>
                              <div className="text-xs line-clamp-1">{message.replyTo.text}</div>
                            </div>
                          )}
                          
                          <p className="text-sm">{message.text}</p>
                        </div>
                        
                        {/* Reply icon outside message bubble */}
                        <button
                          onClick={() => setReplyingTo(message)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity p-2 hover:bg-gray-100 rounded-full flex-shrink-0"
                        >
                          <Reply className="w-4 h-4 text-[#581B98]" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Message Input */}
          <div className="p-4 bg-gradient-to-r from-[#581B98] to-[#9C1DE7]">
            {/* Reply Preview */}
            {replyingTo && (
              <div className="mb-3 bg-white/20 backdrop-blur-sm rounded-lg p-3 flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <Reply className="w-4 h-4 text-white" />
                    <span className="text-xs font-bold text-white">Replying to {replyingTo.senderName}</span>
                  </div>
                  <p className="text-sm text-white/90 line-clamp-2">{replyingTo.text}</p>
                </div>
                <button
                  onClick={() => setReplyingTo(null)}
                  className="ml-2 p-1 hover:bg-white/20 rounded-full transition-colors"
                >
                  <X className="w-4 h-4 text-white" />
                </button>
              </div>
            )}
            
            <div className="flex gap-3 items-center">
              <input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask about patient status..."
                className="flex-1 px-6 py-4 bg-white border-none rounded-full focus:outline-none focus:ring-2 focus:ring-purple-300 text-gray-700 placeholder:text-gray-400 shadow-lg text-base"
              />
              <button
                onClick={handleSendMessage}
                className="bg-gradient-to-r from-[#FF6B4A] to-[#FF8C42] hover:opacity-90 text-white px-8 py-4 rounded-full font-bold text-base transition-opacity shadow-lg uppercase tracking-wide"
              >
                SEND
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}