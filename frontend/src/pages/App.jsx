import React, { useEffect, useState, useRef, useCallback } from "react";
import NavBar from "../components/NavBar";
import ChatWindow from "../components/ChatWindow";
import { apiService } from "../services/api";

const POLL_INTERVAL = 600; // 0.6 seconds
const INITIAL_ERROR_STATE = { visible: false, message: '' };
const DEBOUNCE_DELAY = 300; // 300ms debounce for user input
const CONVERSATION_FETCH_ERROR_DELAY_MS = 10000; // wait 10s before showing fetch errors
const CONVERSATION_FETCH_ERROR_THRESHOLD = Math.ceil(
    CONVERSATION_FETCH_ERROR_DELAY_MS / POLL_INTERVAL
);

function useDebounce(value, delay) {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        return () => {
            clearTimeout(handler);
        };
    }, [value, delay]);

    return debouncedValue;
}

function ManagerPanel() {
    const [task, setTask] = useState('');
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(false);
    const [awaitingConfirm, setAwaitingConfirm] = useState(false);
    const [activeWorkflowId, setActiveWorkflowId] = useState(null);
    const pollingRef = useRef(null);

    const addMessage = (text, type = 'info', extra = {}) => {
        setMessages(prev => [...prev, { text, type, id: Date.now() + Math.random(), ...extra }]);
    };

    const stopPolling = () => {
        if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
        }
    };

    const startPolling = (wfId) => {
        stopPolling();
        pollingRef.current = setInterval(async () => {
            try {
                const { status } = await apiService.managerStatus(wfId);
                if (status === 'waiting_confirm') {
                    stopPolling();
                    let planText = 'Plán je pripravený.';
                    try {
                        const { plan } = await apiService.managerPlan(wfId);
                        if (plan) planText = plan;
                    } catch {}
                    addMessage(planText, 'agent', { showActions: true, workflowId: wfId });
                    setAwaitingConfirm(true);
                    setLoading(false);
                } else if (status === 'done') {
                    stopPolling();
                    addMessage('Workflow dokončený.', 'info');
                    setLoading(false);
                    setAwaitingConfirm(false);
                    setActiveWorkflowId(null);
                } else if (status === 'cancelled') {
                    stopPolling();
                    addMessage('Workflow zrušený.', 'info');
                    setLoading(false);
                    setAwaitingConfirm(false);
                    setActiveWorkflowId(null);
                }
            } catch {}
        }, 1000);
    };

    const handleSend = async () => {
        const trimmed = task.trim();
        if (!trimmed || loading || awaitingConfirm) return;
        setTask('');
        addMessage(trimmed, 'user');
        setLoading(true);
        try {
            const result = await apiService.startManager('auto', trimmed, true);
            setActiveWorkflowId(result.workflow_id);
            addMessage('Pripravujem plán...', 'info');
            startPolling(result.workflow_id);
        } catch (err) {
            addMessage(`Chyba: ${err.message}`, 'error');
            setLoading(false);
        }
    };

    const handleConfirm = async (wfId) => {
        setAwaitingConfirm(false);
        setLoading(true);
        try {
            await apiService.managerConfirm(wfId);
            addMessage('✓ Potvrdené — workflow beží.', 'info');
            startPolling(wfId);
        } catch (err) {
            addMessage(`Chyba: ${err.message}`, 'error');
            setLoading(false);
        }
    };

    const handleCancel = async (wfId) => {
        setAwaitingConfirm(false);
        stopPolling();
        try {
            await apiService.managerCancel(wfId);
            addMessage('✗ Zrušené.', 'info');
        } catch (err) {
            addMessage(`Chyba: ${err.message}`, 'error');
        }
        setActiveWorkflowId(null);
    };

    const handleTerminate = async () => {
        if (!activeWorkflowId) return;
        const wfId = activeWorkflowId;
        stopPolling();
        setLoading(false);
        setAwaitingConfirm(false);
        setActiveWorkflowId(null);
        try {
            await apiService.managerTerminate(wfId);
            addMessage('⛔ Workflow násilne ukončený.', 'info');
        } catch (err) {
            addMessage(`Chyba pri ukončení: ${err.message}`, 'error');
        }
    };

    useEffect(() => () => stopPolling(), []);

    return (
        <div className="border-t border-gray-200 dark:border-gray-700 mt-4 pt-4">
            <p className="text-xs text-gray-400 dark:text-gray-500 mb-2 uppercase tracking-wide">Workflow Manager</p>
            <div className="space-y-2 mb-3">
                {messages.map(m => (
                    <div key={m.id}>
                        <div className={`text-sm px-3 py-2 rounded whitespace-pre-wrap ${
                            m.type === 'user'
                                ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 ml-6'
                                : m.type === 'agent'
                                ? 'bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 mr-6'
                                : m.type === 'error'
                                ? 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                                : 'text-gray-400 dark:text-gray-500 text-xs italic px-1'
                        }`}>{m.text}</div>
                        {m.showActions && (
                            <div className="flex gap-2 mt-1 mr-6">
                                <button
                                    onClick={() => handleConfirm(m.workflowId)}
                                    className="text-sm px-3 py-1 rounded bg-green-600 hover:bg-green-700 text-white font-medium"
                                >
                                    1. Confirm
                                </button>
                                <button
                                    onClick={() => handleCancel(m.workflowId)}
                                    className="text-sm px-3 py-1 rounded bg-red-500 hover:bg-red-600 text-white font-medium"
                                >
                                    2. Cancel
                                </button>
                            </div>
                        )}
                    </div>
                ))}
            </div>
            <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="flex gap-2">
                <input
                    type="text"
                    className="flex-grow border rounded-l px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white focus:outline-none"
                    placeholder="Zadaj workflow task..."
                    value={task}
                    onChange={(e) => setTask(e.target.value)}
                    disabled={loading || awaitingConfirm}
                />
                {activeWorkflowId ? (
                    <button
                        type="button"
                        onClick={handleTerminate}
                        className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-r text-sm"
                    >
                        Stop
                    </button>
                ) : (
                    <button
                        type="submit"
                        disabled={loading || awaitingConfirm || !task.trim()}
                        className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-r text-sm disabled:opacity-50"
                    >
                        {loading ? '...' : 'Run'}
                    </button>
                )}
            </form>
        </div>
    );
}

export default function App() {
    const containerRef = useRef(null);
    const inputRef = useRef(null);
    const pollingRef = useRef(null);
    const scrollTimeoutRef = useRef(null);
    
    const [conversation, setConversation] = useState([]);
    const [lastMessage, setLastMessage] = useState(null);
    const [userInput, setUserInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(INITIAL_ERROR_STATE);
    const [done, setDone] = useState(false);

    const debouncedUserInput = useDebounce(userInput, DEBOUNCE_DELAY);

    const errorTimerRef = useRef(null);
    const conversationFetchErrorCountRef = useRef(0);

    const handleError = useCallback((error, context) => {
        console.error(`${context}:`, error);

        const isConversationFetchError =
            context === "fetching conversation" && (error.status === 404 || error.status === 408);

        if (isConversationFetchError) {
            if (error.status === 404) {
                conversationFetchErrorCountRef.current += 1;

                const hasExceededThreshold =
                    conversationFetchErrorCountRef.current >= CONVERSATION_FETCH_ERROR_THRESHOLD;

                if (!hasExceededThreshold) {
                    return;
                }
            } else {
                // For timeouts or other connectivity errors surface immediately
                conversationFetchErrorCountRef.current = CONVERSATION_FETCH_ERROR_THRESHOLD;
            }
        } else {
            conversationFetchErrorCountRef.current = 0;
        }

        const errorMessage = isConversationFetchError
            ? "Error fetching conversation. Retrying..."
            : `Error ${context.toLowerCase()}. Please try again.`;

        setError(prevError => {
            // If the same 404 error is already being displayed, don't reset state (prevents flickering)
            if (prevError.visible && prevError.message === errorMessage) {
                return prevError;
            }
            return { visible: true, message: errorMessage };
        });

        // Clear any existing timeout
        if (errorTimerRef.current) {
            clearTimeout(errorTimerRef.current);
        }

        // Only auto-dismiss non-404 errors after 3 seconds
        if (!isConversationFetchError) {
            errorTimerRef.current = setTimeout(() => setError(INITIAL_ERROR_STATE), 3000);
        }
    }, []);
    
    
    const clearErrorOnSuccess = useCallback(() => {
        if (errorTimerRef.current) {
            clearTimeout(errorTimerRef.current);
        }
        conversationFetchErrorCountRef.current = 0;
        setError(INITIAL_ERROR_STATE);
    }, []);
    
    const fetchConversationHistory = useCallback(async () => {
        try {
            const data = await apiService.getConversationHistory();
            const newConversation = data.messages || [];
            
            setConversation(prevConversation => 
                JSON.stringify(prevConversation) !== JSON.stringify(newConversation) ? newConversation : prevConversation
            );
    
            if (newConversation.length > 0) {
                const lastMsg = newConversation[newConversation.length - 1];
                const isAgentMessage = lastMsg.actor === "agent";
                
                setLoading(!isAgentMessage);
                setDone(lastMsg.response.next === "done");
    
                setLastMessage(prevLastMessage =>
                    !prevLastMessage || lastMsg.response.response !== prevLastMessage.response.response
                        ? lastMsg
                        : prevLastMessage
                );
            } else {
                setLoading(false);
                setDone(false);
                setLastMessage(null);
            }
    
            // Successfully fetched data, clear any persistent errors
            clearErrorOnSuccess();
        } catch (err) {
            handleError(err, "fetching conversation");
        }
    }, [handleError, clearErrorOnSuccess]);
    
    // Setup polling with cleanup
    useEffect(() => {
        pollingRef.current = setInterval(fetchConversationHistory, POLL_INTERVAL);
        
        return () => clearInterval(pollingRef.current);
    }, [fetchConversationHistory]);
    

    const scrollToBottom = useCallback(() => {
        if (containerRef.current) {
            if (scrollTimeoutRef.current) {
                clearTimeout(scrollTimeoutRef.current);
            }
            
            scrollTimeoutRef.current = setTimeout(() => {
                const element = containerRef.current;
                element.scrollTop = element.scrollHeight;
                scrollTimeoutRef.current = null;
            }, 100);
        }
    }, []);

    const handleContentChange = useCallback(() => {
        scrollToBottom();
    }, [scrollToBottom]);

    useEffect(() => {
        if (lastMessage) {
            scrollToBottom();
        }
    }, [lastMessage, scrollToBottom]);

    useEffect(() => {
        if (inputRef.current && !loading && !done) {
            inputRef.current.focus();
        }
        
        return () => {
            if (scrollTimeoutRef.current) {
                clearTimeout(scrollTimeoutRef.current);
            }
        };
    }, [loading, done]);

    const handleSendMessage = async () => {
        const trimmedInput = userInput.trim();
        if (!trimmedInput) return;
        
        try {
            setLoading(true);
            setError(INITIAL_ERROR_STATE);
            await apiService.sendMessage(trimmedInput);
            setUserInput("");
        } catch (err) {
            handleError(err, "sending message");
            setLoading(false);
        }
    };

    const handleConfirm = async () => {
        try {
            setLoading(true);
            setError(INITIAL_ERROR_STATE);
            await apiService.confirm();
        } catch (err) {
            handleError(err, "confirming action");
            setLoading(false);
        }
    };

    const handleStartNewChat = async () => {
        try {
            setError(INITIAL_ERROR_STATE);
            setLoading(true);
            await apiService.startWorkflow();
            setConversation([]);
            setLastMessage(null);
        } catch (err) {
            handleError(err, "starting new chat");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-screen">
            <NavBar title="Temporal AI Agent 🤖" />

            {error.visible && (
                <div className="fixed top-16 left-1/2 transform -translate-x-1/2 
                    bg-red-500 text-white px-4 py-2 rounded shadow-lg z-50 
                    transition-opacity duration-300">
                    {error.message}
                </div>
            )}

            <div className="flex-grow flex justify-center px-4 py-2 overflow-hidden">
                <div className="w-full max-w-lg flex flex-col overflow-hidden">
                    <div ref={containerRef}
                        className="flex-grow overflow-y-auto pt-10 scroll-smooth"
                        style={{ paddingBottom: '2rem' }}>
                        <ChatWindow
                            conversation={conversation}
                            loading={loading}
                            onConfirm={handleConfirm}
                            onContentChange={handleContentChange}
                        />
                        {done && conversation.length > 0 && (
                            <div className="text-center text-sm text-gray-500 dark:text-gray-400 mt-4
                                animate-fade-in">
                                Chat ended
                            </div>
                        )}
                    </div>
                    <div className="shrink-0 overflow-y-auto" style={{ maxHeight: '40vh', paddingBottom: '7rem' }}>
                        <ManagerPanel />
                    </div>
                </div>
            </div>

            <div className="fixed bottom-0 left-1/2 transform -translate-x-1/2 
                w-full max-w-lg bg-white dark:bg-gray-900 p-4
                border-t border-gray-300 dark:border-gray-700 shadow-lg
                transition-all duration-200"
                style={{ zIndex: 10 }}>
                <form onSubmit={(e) => {
                    e.preventDefault();
                    handleSendMessage();
                }} className="flex items-center">
                    <input
                        ref={inputRef}
                        type="text"
                        className={`flex-grow rounded-l px-3 py-2 border border-gray-300
                            dark:bg-gray-700 dark:border-gray-600 focus:outline-none
                            transition-opacity duration-200
                            ${loading || done ? "opacity-50 cursor-not-allowed" : ""}`}
                        placeholder="Type your message..."
                        value={userInput}
                        onChange={(e) => setUserInput(e.target.value)}
                        disabled={loading || done}
                        aria-label="Type your message"
                    />
                    <button
                        type="submit"
                        className={`bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-r 
                            transition-all duration-200
                            ${loading || done ? "opacity-50 cursor-not-allowed" : ""}`}
                        disabled={loading || done}
                        aria-label="Send message"
                    >
                        Send
                    </button>
                </form>
                
                <div className="text-right mt-3">
                    <button
                        onClick={handleStartNewChat}
                        className={`text-sm underline text-gray-600 dark:text-gray-400 
                            hover:text-gray-800 dark:hover:text-gray-200 
                            transition-all duration-200
                            ${!done ? "opacity-0 cursor-not-allowed" : ""}`}
                        disabled={!done}
                        aria-label="Start new chat"
                    >
                        Start New Chat
                    </button>
                </div>
            </div>
        </div>
    );
}
