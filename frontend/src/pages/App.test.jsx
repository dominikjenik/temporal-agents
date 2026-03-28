import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

// Mock apiService — no real network calls
vi.mock('../services/api', () => ({
    apiService: {
        getTasks: vi.fn().mockResolvedValue([]),
        getHitlState: vi.fn().mockResolvedValue({ result: null, comments: [], status: 'pending' }),
        startManager: vi.fn(),
        managerStatus: vi.fn(),
        managerResult: vi.fn(),
        confirmHitl: vi.fn(),
        commentHitl: vi.fn(),
    },
}));

// Helper: import after mock is registered
async function getApi() {
    const mod = await import('../services/api');
    return mod.apiService;
}

beforeEach(() => {
    vi.clearAllMocks();
});

describe('TaskDetail — task without workflow_id', () => {
    it('shows "Posúdenie nedostupné." and not "Načítavam posúdenie..."', async () => {
        const api = await getApi();
        const task = {
            id: 1, project: 'TEST', title: 'Task bez workflow', priority: 1,
            status: 'pending', type: 'task', workflow_id: null,
        };
        api.getTasks.mockResolvedValue([task]);

        render(<App />);

        // Wait for task to appear in TaskList, then click it
        const btn = await screen.findByText(/Task bez workflow/);
        fireEvent.click(btn);

        // Must show the "not available" message
        expect(await screen.findByText('Posúdenie nedostupné.')).toBeInTheDocument();
        // Must NOT show the loading message
        expect(screen.queryByText('Načítavam posúdenie...')).not.toBeInTheDocument();
    });
});

describe('TaskDetail — task with workflow_id', () => {
    it('shows "Načítavam posúdenie..." while result is null', async () => {
        const api = await getApi();
        const task = {
            id: 2, project: 'TEST', title: 'HITL task', priority: 1,
            status: 'hitl', type: 'hitl', workflow_id: 'wf-abc',
        };
        api.getTasks.mockResolvedValue([task]);
        api.getHitlState.mockResolvedValue({ result: null, comments: [], status: 'pending' });

        render(<App />);

        const btn = await screen.findByText(/HITL task/);
        fireEvent.click(btn);

        expect(await screen.findByText('Načítavam posúdenie...')).toBeInTheDocument();
        expect(screen.queryByText('Posúdenie nedostupné.')).not.toBeInTheDocument();
    });
});

describe('TaskDetail — modal title visibility', () => {
    it('backdrop has items-start and pt-20 so title is not hidden behind NavBar', async () => {
        const api = await getApi();
        const task = {
            id: 3, project: 'PROJ', title: 'Visible title task', priority: 1,
            status: 'hitl', type: 'hitl', workflow_id: 'wf-xyz',
        };
        api.getTasks.mockResolvedValue([task]);

        const { container } = render(<App />);

        const btn = await screen.findByText(/Visible title task/);
        fireEvent.click(btn);

        // Backdrop must use items-start (not items-center) so modal doesn't overlap NavBar
        const backdrop = container.querySelector('.fixed.inset-0.z-50');
        expect(backdrop).not.toBeNull();
        expect(backdrop.className).toContain('items-start');
        expect(backdrop.className).toContain('pt-20');

        // Title text must be present in the modal
        const titles = screen.getAllByText(/Visible title task/);
        expect(titles.length).toBeGreaterThanOrEqual(1);
    });
});
