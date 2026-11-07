/**
 * OmniDev Desktop - Memory Panel Component
 */

import React, { useState, useEffect } from 'react';
import api from '../services/api';

function MemoryPanel({ project }) {
    const [sessionMemories, setSessionMemories] = useState([]);
    const [projectMemories, setProjectMemories] = useState([]);
    const [preferences, setPreferences] = useState([]);
    const [activeTab, setActiveTab] = useState('session');
    const [newMemoryKey, setNewMemoryKey] = useState('');
    const [newMemoryValue, setNewMemoryValue] = useState('');

    useEffect(() => {
        loadSessionMemories();
        if (project) {
            loadProjectMemories();
        }
        loadPreferences();
    }, [project]);

    async function loadSessionMemories() {
        try {
            const memories = await api.listSessionMemories();
            setSessionMemories(memories.memories || []);
        } catch (error) {
            console.error('Failed to load session memories:', error);
        }
    }

    async function loadProjectMemories() {
        if (!project) return;
        try {
            const memories = await api.listProjectMemories(project.id);
            setProjectMemories(memories.memories || []);
        } catch (error) {
            console.error('Failed to load project memories:', error);
        }
    }

    async function loadPreferences() {
        try {
            const prefs = await api.listPreferences('default');
            setPreferences(prefs.preferences || []);
        } catch (error) {
            console.error('Failed to load preferences:', error);
        }
    }

    async function addMemory() {
        if (!newMemoryKey) return;

        try {
            if (activeTab === 'session') {
                await api.setSessionMemory(newMemoryKey, newMemoryValue);
            } else if (activeTab === 'project') {
                await api.setProjectMemory(project.id, newMemoryKey, newMemoryValue);
            }
            setNewMemoryKey('');
            setNewMemoryValue('');

            // Reload
            loadSessionMemories();
            if (project) loadProjectMemories();
        } catch (error) {
            console.error('Failed to add memory:', error);
        }
    }

    async function deleteMemory(key) {
        try {
            await api.deleteSessionMemory(key);
            loadSessionMemories();
        } catch (error) {
            console.error('Failed to delete memory:', error);
        }
    }

    function recallContext() {
        if (!project) return;
        const query = window.prompt('Enter search query:', '');
        if (query) {
            api.recallProjectContext(project.id, query).then(result => {
                console.log('Recall result:', result);
            });
        }
    }

    return (
        <div className="memory-panel">
            <div className="memory-tabs">
                <button
                    className={activeTab === 'session' ? 'active' : ''}
                    onClick={() => setActiveTab('session')}
                >
                    Session
                </button>
                <button
                    className={activeTab === 'project' ? 'active' : ''}
                    onClick={() => setActiveTab('project')}
                    disabled={!project}
                >
                    Project
                </button>
                <button
                    className={activeTab === 'preferences' ? 'active' : ''}
                    onClick={() => setActiveTab('preferences')}
                >
                    Preferences
                </button>
            </div>

            <div className="memory-content">
                {activeTab === 'session' && (
                    <SessionMemoryTab
                        memories={sessionMemories}
                        onAdd={addMemory}
                        onDelete={deleteMemory}
                        newKey={newMemoryKey}
                        newValue={newMemoryValue}
                        onKeyChange={setNewMemoryKey}
                        onValueChange={setNewMemoryValue}
                    />
                )}

                {activeTab === 'project' && project && (
                    <ProjectMemoryTab
                        memories={projectMemories}
                        onAdd={addMemory}
                        onDelete={deleteMemory}
                        onRecall={recallContext}
                        newKey={newMemoryKey}
                        newValue={newMemoryValue}
                        onKeyChange={setNewMemoryKey}
                        onValueChange={setNewMemoryValue}
                    />
                )}

                {activeTab === 'preferences' && (
                    <PreferencesTab
                        preferences={preferences}
                        onUpdate={loadPreferences}
                    />
                )}
            </div>
        </div>
    );
}

function SessionMemoryTab({ memories, onAdd, onDelete, newKey, newValue, onKeyChange, onValueChange }) {
    return (
        <div className="memory-section">
            <h3>Session Memories</h3>
            <div className="memory-form">
                <input
                    type="text"
                    placeholder="Key"
                    value={newKey}
                    onChange={(e) => onKeyChange(e.target.value)}
                    style={{ marginRight: '0.5rem' }}
                />
                <input
                    type="text"
                    placeholder="Value"
                    value={newValue}
                    onChange={(e) => onValueChange(e.target.value)}
                    style={{ flex: 1 }}
                />
                <button onClick={onAdd} style={{ marginLeft: '0.5rem' }}>Add</button>
            </div>
            <ul className="memory-list">
                {memories.map(m => (
                    <li key={m.key} className="memory-item">
                        <strong>{m.key}:</strong> {m.value || JSON.stringify(m.data)}
                        <button onClick={() => onDelete(m.key)} style={{ marginLeft: '0.5rem' }}>×</button>
                    </li>
                ))}
            </ul>
        </div>
    );
}

function ProjectMemoryTab({ memories, onAdd, onDelete, onRecall, newKey, newValue, onKeyChange, onValueChange }) {
    return (
        <div className="memory-section">
            <div className="memory-header">
                <h3>Project Memories</h3>
                <button onClick={onRecall}>🔍 Recall</button>
            </div>
            <div className="memory-form">
                <input
                    type="text"
                    placeholder="Key"
                    value={newKey}
                    onChange={(e) => onKeyChange(e.target.value)}
                    style={{ marginRight: '0.5rem' }}
                />
                <input
                    type="text"
                    placeholder="Value"
                    value={newValue}
                    onChange={(e) => onValueChange(e.target.value)}
                    style={{ flex: 1 }}
                />
                <button onClick={onAdd} style={{ marginLeft: '0.5rem' }}>Add</button>
            </div>
            <ul className="memory-list">
                {memories.map(m => (
                    <li key={m.key} className="memory-item">
                        <strong>{m.key}</strong> <span className="importance">({m.importance || 0})</span>
                        <div style={{ fontSize: '0.8rem', color: '#888' }}>{m.value}</div>
                        <button onClick={() => onDelete(m.key)} style={{ marginLeft: '0.5rem' }}>×</button>
                    </li>
                ))}
            </ul>
        </div>
    );
}

function PreferencesTab({ preferences, onUpdate }) {
    return (
        <div className="memory-section">
            <h3>Long-term Preferences</h3>
            <ul className="memory-list">
                {preferences.map(p => (
                    <li key={`${p.category}-${p.key}`} className="memory-item">
                        <strong>{p.category} / {p.key}:</strong> {p.value || JSON.stringify(p.data)}
                        <span className="scope">[{p.scope}]</span>
                    </li>
                ))}
            </ul>
            <button onClick={onUpdate}>Refresh</button>
        </div>
    );
}

export default MemoryPanel;