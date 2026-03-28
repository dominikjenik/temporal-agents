import React, { useEffect, useState, useRef } from "react";
import NavBar from "../components/NavBar";
import { apiService } from "../services/api";

export default function App() {
    const [task, setTask] = useState('');
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(false);
    const pollingRef = useRef(null);
    const messagesEndRef = useRef(null);

    const addMessage = (text, type = 'info') => {
        setMessages(prev => [...prev, { text, type, id: Date.now() + Math.random() }]);
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
                if (status === 'done') {
                    stopPolling();
                    const { result } = await apiService.managerResult(wfId);
                    addMessage(result, 'agent');
                    setLoading(false);
                }
            } catch {}
        }, 1000);
    };

    const handleSend = async () => {
        const trimmed = task.trim();
        if (!trimmed || loading) return;
        setTask('');
        addMessage(trimmed, 'user');
        setLoading(true);
        try {
            const { workflow_id } = await apiService.startManager(trimmed);
            startPolling(workflow_id);
        } catch (err) {
            addMessage(`Chyba: ${err.message}`, 'error');
            setLoading(false);
        }
    };

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    useEffect(() => () => stopPolling(), []);

    return (
        <div className="flex flex-col h-screen">
            <NavBar title="Temporal AI Agent" />

            <div className="flex-grow flex justify-center px-4 py-2 overflow-hidden">
                <div className="w-full max-w-lg flex flex-col overflow-hidden">
                    <div className="flex-grow overflow-y-auto py-4 space-y-2">
                        {messages.map(m => (
                            <div key={m.id} className={`text-sm px-3 py-2 rounded whitespace-pre-wrap ${
                                m.type === 'user'
                                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 ml-6'
                                    : m.type === 'agent'
                                    ? 'bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 mr-6'
                                    : m.type === 'error'
                                    ? 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                                    : 'text-gray-400 dark:text-gray-500 text-xs italic px-1'
                            }`}>{m.text}</div>
                        ))}
                        {loading && (
                            <div className="text-xs text-gray-400 dark:text-gray-500 italic px-1">
                                Spracovávam...
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>
                </div>
            </div>

            <div className="flex justify-center px-4 pb-6">
                <form
                    onSubmit={(e) => { e.preventDefault(); handleSend(); }}
                    className="flex w-full max-w-lg"
                >
                    <input
                        type="text"
                        className="flex-grow border rounded-l px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white focus:outline-none"
                        placeholder="Zadaj otázku..."
                        value={task}
                        onChange={(e) => setTask(e.target.value)}
                        disabled={loading}
                        autoFocus
                    />
                    <button
                        type="submit"
                        disabled={loading || !task.trim()}
                        className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-r text-sm disabled:opacity-50"
                    >
                        {loading ? '...' : 'Pošli'}
                    </button>
                </form>
            </div>
        </div>
    );
}
