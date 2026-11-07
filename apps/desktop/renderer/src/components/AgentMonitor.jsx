/**
 * OmniDev Desktop - Agent Monitor Component
 */

import React from 'react';

function AgentMonitor({ agents, selectedAgent }) {
    const [showDetail, setShowDetail] = React.useState(false);

    return (
        <div className="agent-monitor">
            <div
                className="agent-item active"
                onClick={() => setShowDetail(!showDetail)}
                style={{ cursor: 'pointer' }}
            >
                <div className="agent-status-indicator active" />
                <span style={{ flex: 1 }}>{selectedAgent?.name || 'No Agent'}</span>
                <span style={{ fontSize: '0.75rem' }}>{showDetail ? '▲' : '▼'}</span>
            </div>

            {showDetail && selectedAgent && (
                <div style={{ fontSize: '0.75rem', padding: '0.5rem', marginTop: '0.25rem' }}>
                    <div>Model: {selectedAgent.model}</div>
                    <div>Provider: {selectedAgent.provider}</div>
                    <div>Tools: {selectedAgent.tool_count || 0}</div>
                    <div>Max Steps: {selectedAgent.max_steps}</div>
                </div>
            )}

            <div style={{ fontSize: '0.75rem', color: '#888', marginTop: '0.5rem' }}>
                {agents.length} agent{agents.length !== 1 ? 's' : ''}
            </div>
        </div>
    );
}

export default AgentMonitor;