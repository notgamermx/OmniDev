/**
 * OmniDev Desktop - Main App Component
 */

import React, { useState, useEffect } from 'react';
import api from './services/api';
import Chat from './components/Chat';
import FileExplorer from './components/FileExplorer';
import CodeEditor from './components/CodeEditor';
import TerminalPanel from './components/TerminalPanel';
import AgentMonitor from './components/AgentMonitor';
import MemoryPanel from './components/MemoryPanel';

function App() {
    const [currentView, setCurrentView] = useState('chat');
    const [selectedFile, setSelectedFile] = useState(null);
    const [agents, setAgents] = useState([]);
    const [selectedAgent, setSelectedAgent] = useState(null);
    const [selectedProject, setSelectedProject] = useState(null);
    const [currentSessionId] = useState(`session-${Date.now()}`);

    // Load agents on mount
    useEffect(() => {
        loadAgents();
    }, []);

    async function loadAgents() {
        try {
            const response = await api.listAgents();
            setAgents(response.agents || []);
            if (response.agents?.length > 0) {
                setSelectedAgent(response.agents[0]);
            }
        } catch (error) {
            console.error('Failed to load agents:', error);
        }
    }

    async function createAgent(agentData) {
        try {
            const response = await api.createAgent(agentData);
            await loadAgents();
            setSelectedAgent(response);
            return response;
        } catch (error) {
            console.error('Failed to create agent:', error);
            throw error;
        }
    }

    async function createTask(taskData) {
        try {
            return await api.createTask(taskData);
        } catch (error) {
            console.error('Failed to create task:', error);
            throw error;
        }
    }

    async function fileOperation(operation, path, content = null) {
        try {
            switch (operation) {
                case 'read':
                    return await api.readFile(path);
                case 'write':
                    return await api.writeFile(path, content);
                case 'list':
                    return await api.listFiles(path);
                default:
                    throw new Error(`Unknown operation: ${operation}`);
            }
        } catch (error) {
            console.error(`File operation failed: ${operation}`, error);
            throw error;
        }
    }

    const navigation = [
        { id: 'chat', label: 'Chat', icon: '💬' },
        { id: 'files', label: 'Files', icon: '📁' },
        { id: 'editor', label: 'Editor', icon: '📝' },
        { id: 'terminal', label: 'Terminal', icon: '⚡' },
        { id: 'agents', label: 'Agents', icon: '🤖' },
        { id: 'memory', label: 'Memory', icon: '🧠' }
    ];

    return (
        <div className="app-container">
            {/* Sidebar Navigation */}
            <nav className="sidebar">
                <div className="app-logo">
                    <span className="logo-icon">🧠</span>
                    <span>OmniDev</span>
                </div>
                <ul className="nav-list">
                    {navigation.map(item => (
                        <li
                            key={item.id}
                            className={`nav-item ${currentView === item.id ? 'active' : ''}`}
                            onClick={() => {
                                setCurrentView(item.id);
                                if (item.id === 'files') {
                                    setSelectedFile(null);
                                }
                            }}
                        >
                            <span className="nav-icon">{item.icon}</span>
                            <span className="nav-label">{item.label}</span>
                        </li>
                    ))}
                </ul>
                <div className="sidebar-footer">
                    <AgentMonitor agents={agents} selectedAgent={selectedAgent} />
                </div>
            </nav>

            {/* Main Content Area */}
            <main className="main-content">
                <header className="header">
                    <h1>{navigation.find(n => n.id === currentView)?.label || 'OmniDev'}</h1>
                </header>

                <section className="content-area">
                    {currentView === 'chat' && (
                        <Chat
                            agent={selectedAgent}
                            agents={agents}
                            onSelectAgent={setSelectedAgent}
                            file={selectedFile}
                            onFileSelect={setSelectedFile}
                            createTask={createTask}
                            api={api}
                        />
                    )}

                    {currentView === 'files' && (
                        <FileExplorer
                            selectedFile={selectedFile}
                            onFileSelect={setSelectedFile}
                            fileOperation={fileOperation}
                        />
                    )}

                    {currentView === 'editor' && (
                        <CodeEditor
                            file={selectedFile}
                            fileOperation={fileOperation}
                        />
                    )}

                    {currentView === 'terminal' && (
                        <TerminalPanel />
                    )}

                    {currentView === 'agents' && (
                        <div className="agents-view">
                            <div className="agents-header">
                                <h2>Agents</h2>
                            </div>
                            {/* Agent management UI would go here */}
                            <div style={{ padding: '1rem' }}>
                                <p>Agent management panel</p>
                                <ul>
                                    {agents.map(a => (
                                        <li key={a.id}>{a.name} ({a.provider}:{a.model})</li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    )}

                    {currentView === 'memory' && (
                        <MemoryPanel
                            project={selectedProject}
                            sessionId={currentSessionId}
                        />
                    )}
                </section>
            </main>
        </div>
    );
}

export default App;