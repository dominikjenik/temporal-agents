import React, { useEffect, useRef, useState } from "react";
import NavBar from "../components/NavBar";
import { apiService } from "../services/api";

// ---------------------------------------------------------------------------
// TaskList — top panel, polls every second, always visible
// ---------------------------------------------------------------------------

function TaskList({ onSelect }) {
    const [tasks, setTasks] = useState([]);

    useEffect(() => {
        let alive = true;
        const poll = async () => {
            try {
                const data = await apiService.getTasks();
                if (alive) setTasks(data);
            } catch {}
        };
        poll();
        const id = setInterval(poll, 1000);
        return () => { alive = false; clearInterval(id); };
    }, []);

    return (
        <div className="border-b dark:border-gray-700 px-4 py-2 min-h-10 max-h-40 overflow-y-auto bg-gray-50 dark:bg-gray-900">
            {tasks.length === 0 ? (
                <p className="text-xs text-gray-400 dark:text-gray-600 italic">Žiadne úlohy.</p>
            ) : tasks.map(task => (
                <button
                    key={task.id}
                    onClick={() => onSelect(task)}
                    className={`w-full text-left text-xs px-2 py-1 rounded mb-1 flex justify-between items-center
                        ${task.type === 'hitl'
                            ? 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 animate-pulse border border-yellow-200 dark:border-yellow-700'
                            : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-600'
                        } hover:opacity-80`}
                >
                    <span className="truncate">[{task.project}] {task.title}</span>
                    <span className="ml-2 shrink-0 font-mono text-gray-400">p{task.priority} · {task.status}</span>
                </button>
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// TaskDetail — modal overlay with HITL conversation
// ---------------------------------------------------------------------------

function TaskDetail({ task, onClose }) {
    const [hitlState, setHitlState] = useState(null);
    const [comment, setComment] = useState('');
    const [sending, setSending] = useState(false);
    const [confirming, setConfirming] = useState(false);
    const [done, setDone] = useState(false);

    useEffect(() => {
        if (!task.workflow_id) return;
        let alive = true;
        const poll = async () => {
            try {
                const data = await apiService.getHitlState(task.workflow_id);
                if (alive) setHitlState(data);
            } catch {}
        };
        poll();
        const id = setInterval(poll, 1000);
        return () => { alive = false; clearInterval(id); };
    }, [task.workflow_id]);

    const result = hitlState?.result ? JSON.parse(hitlState.result) : null;
    const comments = hitlState?.comments ?? [];

    const handleComment = async () => {
        const trimmed = comment.trim();
        if (!trimmed || !task.workflow_id) return;
        setSending(true);
        try {
            await apiService.commentHitl(task.workflow_id, trimmed);
            setComment('');
        } catch (err) {
            alert(err.message);
        } finally {
            setSending(false);
        }
    };

    const handleConfirm = async () => {
        if (!task.workflow_id) return;
        setConfirming(true);
        try {
            await apiService.confirmHitl(task.workflow_id);
            setDone(true);
            setTimeout(onClose, 800);
        } catch (err) {
            alert(err.message);
        } finally {
            setConfirming(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
            <div
                className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-lg mx-4 p-4 flex flex-col gap-3 max-h-[80vh] overflow-y-auto"
                onClick={e => e.stopPropagation()}
            >
                <div className="flex justify-between items-center">
                    <h2 className="font-semibold text-sm dark:text-white truncate">
                        [{task.project}] {task.title}
                    </h2>
                    <button
                        onClick={onClose}
                        className="ml-2 shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl leading-none"
                    >
                        &times;
                    </button>
                </div>

                {result ? (
                    <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded p-3 text-sm">
                        <span className="font-semibold text-yellow-700 dark:text-yellow-300 uppercase text-xs tracking-wide">
                            {result.intent}
                        </span>
                        <p className="mt-1 text-yellow-800 dark:text-yellow-200">{result.payload}</p>
                    </div>
                ) : (
                    <p className="text-xs text-gray-400 italic">Načítavam posúdenie...</p>
                )}

                {comments.length > 0 && (
                    <div className="flex flex-col gap-1 border-t dark:border-gray-700 pt-2">
                        {comments.map((c, i) => (
                            <React.Fragment key={i}>
                                <div className="text-xs bg-blue-50 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 rounded px-2 py-1 ml-6">
                                    {c.user}
                                </div>
                                <div className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded px-2 py-1 mr-6">
                                    {c.bot}
                                </div>
                            </React.Fragment>
                        ))}
                    </div>
                )}

                {done ? (
                    <p className="text-green-600 dark:text-green-400 text-sm text-center font-medium">Potvrdené.</p>
                ) : (
                    <div className="flex flex-col gap-2 border-t dark:border-gray-700 pt-2">
                        <button
                            onClick={handleConfirm}
                            disabled={confirming || !task.workflow_id}
                            className="bg-green-600 hover:bg-green-700 text-white text-sm px-4 py-2 rounded disabled:opacity-50"
                        >
                            {confirming ? '...' : 'OK'}
                        </button>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                placeholder="Komentár (povinný)"
                                value={comment}
                                onChange={e => setComment(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && handleComment()}
                                className="flex-grow border rounded px-2 py-1 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white focus:outline-none"
                            />
                            <button
                                onClick={handleComment}
                                disabled={!comment.trim() || sending}
                                className="bg-gray-500 hover:bg-gray-600 text-white text-sm px-3 py-1 rounded disabled:opacity-40"
                            >
                                {sending ? '...' : 'Komentovať'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
    const [task, setTask] = useState('');
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedTask, setSelectedTask] = useState(null);
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
        <div className="flex flex-col h-screen pt-16">
            <NavBar title="Temporal AI Agent" />

            <TaskList onSelect={setSelectedTask} />

            {selectedTask && (
                <TaskDetail task={selectedTask} onClose={() => setSelectedTask(null)} />
            )}

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
