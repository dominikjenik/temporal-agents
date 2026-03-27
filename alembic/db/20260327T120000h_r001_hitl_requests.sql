CREATE TABLE IF NOT EXISTS hitl_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id TEXT NOT NULL,
    description TEXT NOT NULL,
    priority INTEGER DEFAULT 5,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
