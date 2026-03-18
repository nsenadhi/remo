import { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { Send, Reply, X } from 'lucide-react';

interface Message {
  id: string;
  sender: 'doctor' | 'patient' | 'remoni';
  text: string;
  timestamp: string;
  date: string;
  senderName: string;
  replyTo?: {
    id: string;
    senderName: string;
    text: string;
  };
  patient_id?: string;
}

interface ChatroomProps {
  onBack?: () => void;
  onLogout?: () => void;
}

export function Chatroom({ onBack, onLogout }: ChatroomProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [currentUser, setCurrentUser] = useState<'doctor' | 'patient' | 'remoni'>('doctor');
  const [currentUserName, setCurrentUserName] = useState<string>('Doctor');
  const [replyingTo, setReplyingTo] = useState<Message | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [headerTitle, setHeaderTitle] = useState<string>('Chat');
  const [headerDescription, setHeaderDescription] = useState<string>('');
  const [patientId, setPatientId] = useState<string>('00001');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const initialScrollRef = useRef(true);
  const userAtBottomRef = useRef(true);
  const patientIdRef = useRef('00001');
  const savedScrollRef = useRef<number | null>(null);
  const headerIcon =
    currentUser === 'doctor'
      ? '/static/images/patient-4.png'
      : currentUser === 'patient'
        ? '/static/images/doctor-3.png'
        : 'https://img.icons8.com/color/48/000000/medical-doctor.png';

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  useLayoutEffect(() => {
    if (initialScrollRef.current) {
      const el = messagesContainerRef.current;
      if (el && savedScrollRef.current !== null) {
        const maxScroll = Math.max(0, el.scrollHeight - el.clientHeight);
        el.scrollTop = Math.min(savedScrollRef.current, maxScroll);
      } else {
        scrollToBottom('auto');
      }
      initialScrollRef.current = false;
      return;
    }
    if (userAtBottomRef.current) {
      scrollToBottom('auto');
    }
  }, [messages]);

  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      const threshold = 40;
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      userAtBottomRef.current = distanceFromBottom <= threshold;
      try {
        const key = `chatroom_scroll_${currentUser}_${patientIdRef.current}`;
        sessionStorage.setItem(key, String(el.scrollTop));
      } catch {
        // ignore
      }
    };
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    patientIdRef.current = params.get('patient_id') || '00001';
    setPatientId(patientIdRef.current);
    const patientNameParam = params.get('patient_name');
    const prefillFromQuery = params.get('prefill');

    let prefillMessage = '';
    if (prefillFromQuery) {
      try {
        prefillMessage = decodeURIComponent(prefillFromQuery);
      } catch {
        prefillMessage = prefillFromQuery;
      }
    }

    const loadSession = async () => {
      try {
        const res = await fetch('/api/chatroom/session');
        const data = await res.json();
        if (data && data.role) {
          setCurrentUser(data.role);
          setCurrentUserName(data.name || (data.role === 'doctor' ? 'Doctor' : 'Patient'));
          if (data.role === 'doctor') {
            const patientLabel = patientNameParam ? `Patient ${patientIdRef.current} - ${patientNameParam}` : `Patient ${patientIdRef.current}`;
            setHeaderTitle(patientLabel);
            setHeaderDescription('');
          } else if (data.role === 'patient') {
            setHeaderTitle('Doctor');
            setHeaderDescription('');
          } else {
            setHeaderTitle('Chat');
            setHeaderDescription('');
          }
        }
      } catch {
        // ignore
      }
    };

    const loadMessages = async () => {
      try {
        const res = await fetch('/api/chatroom/messages?patient_id=' + patientIdRef.current);
        const data = await res.json();
        if (data && data.messages) {
          setMessages(data.messages);
        }
      } catch {
        // ignore
      }
    };

    loadSession();
    loadMessages();
    if (!prefillMessage) {
      try {
        const key = `chat_prefill_${patientIdRef.current}`;
        prefillMessage = localStorage.getItem(key) || '';
        if (prefillMessage) {
          localStorage.removeItem(key);
        }
      } catch {
        // ignore storage failures
      }
    }
    if (prefillMessage) {
      setNewMessage(prefillMessage);
    }
    const interval = setInterval(loadMessages, 4000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    try {
      const key = `chatroom_scroll_${currentUser}_${patientIdRef.current}`;
      const raw = sessionStorage.getItem(key);
      savedScrollRef.current = raw ? parseInt(raw, 10) : null;
    } catch {
      savedScrollRef.current = null;
    }
    initialScrollRef.current = true;
  }, [currentUser, patientId]);

  useEffect(() => {
    if (!messages.length) return;
    try {
      const key = `chatroom_last_seen_${currentUser}_${patientIdRef.current}`;
      localStorage.setItem(key, new Date().toISOString());
    } catch {
      // ignore
    }
  }, [messages, currentUser]);

  const handleSendMessage = async () => {
    if (newMessage.trim() === '') return;

    const messageText = newMessage.trim();
    setNewMessage('');

    try {
      await fetch('/api/chatroom/messages?patient_id=' + patientIdRef.current, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sender: currentUser,
          text: messageText,
          senderName: currentUserName,
          replyTo: replyingTo
            ? {
                id: replyingTo.id,
                senderName: replyingTo.senderName,
                text: replyingTo.text,
              }
            : null
        })
      });
    } catch {
      // ignore
    }

    try {
      const res = await fetch('/api/chatroom/messages?patient_id=' + patientIdRef.current);
      const data = await res.json();
      if (data && data.messages) {
        setMessages(data.messages);
      }
    } catch {
      // ignore
    }

    setReplyingTo(null);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
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

  const normalizeMessageText = (text: string) => text.replace(/\n{2,}/g, '\n').trim();

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: '#f9f9f9'
    }}>
      {/* Header - Exact match to chatbox__header */}
      <div style={{
        position: 'sticky',
        top: 0,
        background: 'linear-gradient(93.12deg, #581B98 0.52%, #9C1DE7 100%)',
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'flex-start',
        padding: '24px 25px',
        boxShadow: '0px 10px 15px rgba(0, 0, 0, 0.1)',
        zIndex: 100,
        flexShrink: 0
      }}>
        <div style={{ marginRight: '20px' }}>
          <img
            src={headerIcon}
            alt="Icon"
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              objectFit: 'cover'
            }}
          />
        </div>
        <div>
          <h4 style={{
            fontSize: '1.5rem',
            color: 'white',
            fontWeight: 600,
            margin: 0,
            lineHeight: 1.2
          }}>
            {headerTitle}
          </h4>
          {headerDescription && (
            <p style={{
              color: 'rgba(255, 255, 255, 0.8)',
              fontSize: '0.875rem',
              margin: '2px 0 0 0',
              lineHeight: 1.2
            }}>
              {headerDescription}
            </p>
          )}
        </div>
      </div>

      {/* Messages Container - Exact match to chatbox__messages */}
      <div
        ref={messagesContainerRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          background: '#f9f9f9'
        }}
      >
        {messages.map((message, index) => {
          const isOwnMessage = message.sender === currentUser;
          const previousMessage = index > 0 ? messages[index - 1] : null;
          const showDateSeparator = shouldShowDateSeparator(message, previousMessage);

          return (
            <div key={message.id}>
              {showDateSeparator && (
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  margin: '16px 0'
                }}>
                  <div style={{
                    background: '#E0E0E0',
                    color: '#666',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    padding: '4px 16px',
                    borderRadius: '999px'
                  }}>
                    {formatDate(message.date)}
                  </div>
                </div>
              )}

              <div style={{
                display: 'flex',
                width: '100%',
                justifyContent: isOwnMessage ? 'flex-end' : 'flex-start'
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  maxWidth: '75%',
                  position: 'relative'
                }}
                onMouseEnter={() => setHoveredId(message.id)}
                onMouseLeave={() => setHoveredId(null)}>
                  {isOwnMessage && (
                    <button
                      onClick={() => setReplyingTo(message)}
                      style={{
                        padding: '8px',
                        background: 'transparent',
                        border: 'none',
                        borderRadius: '50%',
                        cursor: 'pointer',
                        opacity: hoveredId === message.id ? 1 : 0,
                        visibility: hoveredId === message.id ? 'visible' : 'hidden',
                        transition: 'all 0.2s'
                      }}
                      className="hover:bg-gray-100"
                    >
                      <Reply style={{ width: '16px', height: '16px', color: '#581B98' }} />
                    </button>
                  )}

                  <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: isOwnMessage ? 'flex-end' : 'flex-start'
                  }}>
                    <div style={{
                      fontSize: '0.75rem',
                      color: '#666',
                      marginBottom: '4px'
                    }}>
                      {formatMessageDateTime(message.date, message.timestamp)}
                    </div>
                    
                    {/* Message Bubble - Exact match to messages__item */}
                    <div
                      onClick={() => setReplyingTo(message)}
                      style={{
                        padding: '12px 16px',
                        borderRadius: '12px',
                        maxWidth: '100%',
                        wordWrap: 'break-word',
                        animation: 'fadeIn 0.3s ease-in',
                        lineHeight: 1.3,
                        alignSelf: isOwnMessage ? 'flex-end' : 'flex-start',
                        background: isOwnMessage ? '#581B98' : '#E0E0E0',
                        color: isOwnMessage ? 'white' : '#333',
                        borderBottomRightRadius: isOwnMessage ? '4px' : '12px',
                        borderBottomLeftRadius: isOwnMessage ? '12px' : '4px',
                        cursor: 'pointer',
                        transition: 'opacity 0.2s'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
                      onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                      onMouseOver={() => setHoveredId(message.id)}
                      onMouseOut={() => setHoveredId(null)}
                    >
                      {message.replyTo && (
                        <div style={{
                          marginBottom: '8px',
                          paddingBottom: '8px',
                          borderLeft: '2px solid rgba(255, 255, 255, 0.3)',
                          paddingLeft: '8px',
                          opacity: 0.8
                        }}>
                          <div style={{ fontSize: '0.75rem', fontWeight: 700 }}>
                            {message.replyTo.senderName}
                          </div>
                          <div style={{
                            fontSize: '0.75rem',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }}>
                            {normalizeMessageText(message.replyTo.text)}
                          </div>
                        </div>
                      )}
                      <p style={{ fontSize: '0.875rem', margin: 0, whiteSpace: 'pre-line' }}>
                        {normalizeMessageText(message.text)}
                      </p>
                    </div>
                  </div>

                  {!isOwnMessage && (
                    <button
                      onClick={() => setReplyingTo(message)}
                      style={{
                        padding: '8px',
                        background: 'transparent',
                        border: 'none',
                        borderRadius: '50%',
                        cursor: 'pointer',
                        opacity: hoveredId === message.id ? 1 : 0,
                        visibility: hoveredId === message.id ? 'visible' : 'hidden',
                        transition: 'all 0.2s'
                      }}
                      className="hover:bg-gray-100"
                    >
                      <Reply style={{ width: '16px', height: '16px', color: '#581B98' }} />
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Footer - Exact match to chatbox__footer */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        padding: '16px 22px',
        background: 'linear-gradient(268.91deg, #581B98 -2.14%, #9C1DE7 99.69%)',
        boxShadow: '0px -10px 15px rgba(0, 0, 0, 0.1)',
        flexShrink: 0
      }}>
        {replyingTo && (
          <div style={{
            marginBottom: '12px',
            background: 'rgba(255, 255, 255, 0.2)',
            backdropFilter: 'blur(10px)',
            borderRadius: '8px',
            padding: '12px',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between'
          }}>
            <div style={{ flex: 1 }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '4px'
              }}>
                <Reply style={{ width: '16px', height: '16px', color: 'white' }} />
                <span style={{
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  color: 'white'
                }}>
                  Replying to {replyingTo.senderName}
                </span>
              </div>
              <p style={{
                fontSize: '0.875rem',
                color: 'rgba(255, 255, 255, 0.9)',
                margin: 0,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical'
              }}>
                {replyingTo.text}
              </p>
            </div>
            <button
              onClick={() => setReplyingTo(null)}
              style={{
                marginLeft: '8px',
                padding: '4px',
                background: 'transparent',
                border: 'none',
                borderRadius: '50%',
                cursor: 'pointer',
                transition: 'background 0.2s'
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.2)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <X style={{ width: '16px', height: '16px', color: 'white' }} />
            </button>
          </div>
        )}

        <div style={{
          display: 'flex',
          gap: '14px',
          alignItems: 'center'
        }}>
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={currentUser === 'patient' ? 'Ask from doctor...' : 'Ask about patient status...'}
            style={{
              flex: 1,
              border: 'none',
              padding: '14px 22px',
              borderRadius: '999px',
              background: '#ffffff',
              textAlign: 'left',
              fontSize: '1.05rem',
              outline: 'none',
              fontFamily: 'Nunito, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
              boxShadow: '0 6px 16px rgba(0, 0, 0, 0.12)'
            }}
            onFocus={(e) => {
              e.target.style.boxShadow = '0 0 0 2px rgba(255, 255, 255, 0.3)';
            }}
            onBlur={(e) => {
              e.target.style.boxShadow = '0 6px 16px rgba(0, 0, 0, 0.12)';
            }}
          />
          <button
            onClick={handleSendMessage}
            style={{
              padding: '14px 30px',
              background: 'linear-gradient(135deg, #FF6B35 0%, #FF8E53 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '999px',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '1.05rem',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 12px rgba(255, 107, 53, 0.3)',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'linear-gradient(135deg, #FF8E53 0%, #FFA07A 100%)';
              e.currentTarget.style.transform = 'scale(1.05)';
              e.currentTarget.style.boxShadow = '0 6px 16px rgba(255, 107, 53, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'linear-gradient(135deg, #FF6B35 0%, #FF8E53 100%)';
              e.currentTarget.style.transform = 'scale(1)';
              e.currentTarget.style.boxShadow = '0 4px 12px rgba(255, 107, 53, 0.3)';
            }}
            onMouseDown={(e) => {
              e.currentTarget.style.transform = 'scale(0.98)';
              e.currentTarget.style.boxShadow = '0 2px 8px rgba(255, 107, 53, 0.3)';
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.transform = 'scale(1.05)';
              e.currentTarget.style.boxShadow = '0 6px 16px rgba(255, 107, 53, 0.4)';
            }}
          >
            <span>Send</span>
          </button>
        </div>
      </div>
    </div>
  );
}
