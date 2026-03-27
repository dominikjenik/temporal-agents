const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

const resolveRequestTimeout = () => {
    const env = typeof import.meta !== 'undefined' ? import.meta.env : undefined;
    const configured = env?.VITE_API_TIMEOUT_MS;
    const parsed = Number.parseInt(configured, 10);
    if (Number.isFinite(parsed) && parsed > 0) {
        return parsed;
    }
    return 15000;
};

const REQUEST_TIMEOUT_MS = resolveRequestTimeout(); // default to 15s, overridable via Vite env

class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
        this.name = 'ApiError';
    }
}

async function handleResponse(response) {
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ApiError(
            errorData.message || 'An error occurred',
            response.status
        );
    }
    return response.json();
}

async function fetchWithTimeout(url, options = {}, timeout = REQUEST_TIMEOUT_MS) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        return await fetch(url, { ...options, signal: controller.signal });
    } catch (error) {
        if (error.name === 'AbortError') {
            throw new ApiError('Request timed out', 408);
        }
        throw error;
    } finally {
        clearTimeout(timeoutId);
    }
}

export const apiService = {
    async getConversationHistory() {
        try {
            const res = await fetchWithTimeout(`${API_BASE_URL}/get-conversation-history`);
            return handleResponse(res);
        } catch (error) {
            if (error instanceof ApiError) {
                throw error;
            }
            throw new ApiError(
                'Failed to fetch conversation history',
                error.status || 500
            );
        }
    },

    async sendMessage(message) {
        if (!message?.trim()) {
            throw new ApiError('Message cannot be empty', 400);
        }

        try {
            const res = await fetchWithTimeout(
                `${API_BASE_URL}/send-prompt?prompt=${encodeURIComponent(message)}`,
                { 
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }
            );
            return handleResponse(res);
        } catch (error) {
            if (error instanceof ApiError) {
                throw error;
            }
            throw new ApiError(
                'Failed to send message',
                error.status || 500
            );
        }
    },

    async startWorkflow() {
        try {
            const res = await fetchWithTimeout(
                `${API_BASE_URL}/start-workflow`,
                { 
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }
            );
            return handleResponse(res);
        } catch (error) {
            if (error instanceof ApiError) {
                throw error;
            }
            throw new ApiError(
                'Failed to start workflow',
                error.status || 500
            );
        }
    },

    async confirm() {
        try {
            const res = await fetchWithTimeout(`${API_BASE_URL}/confirm`, { 
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            return handleResponse(res);
        } catch (error) {
            if (error instanceof ApiError) {
                throw error;
            }
            throw new ApiError(
                'Failed to confirm action',
                error.status || 500
            );
        }
    },

    async startManager(project, task, requireConfirm = true) {
        try {
            const res = await fetchWithTimeout(
                `${API_BASE_URL}/start-manager`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project, task, require_confirm: requireConfirm })
                }
            );
            return handleResponse(res);
        } catch (error) {
            if (error instanceof ApiError) throw error;
            throw new ApiError('Failed to start manager workflow', error.status || 500);
        }
    },

    async managerConfirm(workflowId) {
        try {
            const res = await fetchWithTimeout(
                `${API_BASE_URL}/manager-confirm/${encodeURIComponent(workflowId)}`,
                { method: 'POST', headers: { 'Content-Type': 'application/json' } }
            );
            return handleResponse(res);
        } catch (error) {
            if (error instanceof ApiError) throw error;
            throw new ApiError('Failed to confirm manager workflow', error.status || 500);
        }
    },

    async managerCancel(workflowId) {
        try {
            const res = await fetchWithTimeout(
                `${API_BASE_URL}/manager-cancel/${encodeURIComponent(workflowId)}`,
                { method: 'POST', headers: { 'Content-Type': 'application/json' } }
            );
            return handleResponse(res);
        } catch (error) {
            if (error instanceof ApiError) throw error;
            throw new ApiError('Failed to cancel manager workflow', error.status || 500);
        }
    },

    async managerStatus(workflowId) {
        try {
            const res = await fetchWithTimeout(
                `${API_BASE_URL}/manager-status/${encodeURIComponent(workflowId)}`
            );
            return handleResponse(res);
        } catch (error) {
            if (error instanceof ApiError) throw error;
            throw new ApiError('Failed to fetch manager status', error.status || 500);
        }
    },

    async managerTerminate(workflowId) {
        try {
            const res = await fetchWithTimeout(
                `${API_BASE_URL}/manager-terminate/${encodeURIComponent(workflowId)}`,
                { method: 'POST', headers: { 'Content-Type': 'application/json' } }
            );
            return handleResponse(res);
        } catch (error) {
            if (error instanceof ApiError) throw error;
            throw new ApiError('Failed to terminate workflow', error.status || 500);
        }
    },

    async managerPlan(workflowId) {
        try {
            const res = await fetchWithTimeout(
                `${API_BASE_URL}/manager-plan/${encodeURIComponent(workflowId)}`
            );
            return handleResponse(res);
        } catch (error) {
            if (error instanceof ApiError) throw error;
            throw new ApiError('Failed to fetch manager plan', error.status || 500);
        }
    }
};
