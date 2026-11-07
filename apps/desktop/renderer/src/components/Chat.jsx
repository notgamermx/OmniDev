/**
 * OmniDev Desktop - Chat Component
 */

import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';

function Chat({ agent, agents, onSelectAgent, file, onFileSelect, createTask, api: apiService }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef(null);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    function scrollToBottom() {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }

    async function handleSend(e) {
        e.preventDefault();
        if (!input.trim()) return;

        const userMessage = {
            role: 'user',
            content: input
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            // Create task for execution
            const taskData = {
                agent_id: agent?.id || agents[0]?.id,
                title: `Chat: ${input.substring(0, 50)}...`,
                description: input,
                max_steps: 10
            };

            const task = await apiService.createTask(taskData);

            // Execute task
            const result = await apiService.executeTask(task.id);

            const agentResponse = {
                role: 'assistant',
                content: result.result || 'Task completed',
                task_id: task.id
            };

            setMessages(prev => [...prev, agentResponse]);
        } catch (error) {
            console.error('Error:', error);
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: `Error: ${error.message}`
            }]);
        } finally {
            setIsLoading(false);
        }
    }

    return (
        <div className="chat-container">
            <div className="chat-messages">
                {messages.length === 0 && (
                    <div className="message agent">
                        <div className="message-content">
                            <p>Hello! I'm OmniDev, your AI development assistant.</p>
                            <p>I can help you with coding, debugging, and project understanding.</p>
                            <p>Selected file: {file?.path || 'None'}</p>
                            <p>Try asking me to analyze a file or write some code!</p>
                        </div>
                    </div>
                )}

                {messages.map((msg, idx) => (
                    <div key={idx} className={`message ${msg.role}`}>
                        <div className="message-content">
                            {msg.content}
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="message agent">
                        <div className="message-content">Thinking...</div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSend} className="chat-input">
                <select
                    value={agent?.id || ''}
                    onChange={(e) => onSelectAgent(parseInt(e.target.value))}
                    style={{ marginRight: '0.5rem' }}
                >
                    <option value="">Select Agent</option>
                    {agents.map(a => (
                        <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                </select>

                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask me anything..."
                    disabled={isLoading}
                    style={{
                        flex: 1,
                        padding: '0.5rem',
                        borderRadius: '0.25rem',
                        border: '1px solid #0f3460',
                        background: '#16213e',
                        color: '#fff'
                    }}
                />

                <button
                    type="submit"
                    disabled={isLoading}
                    style={{
                        marginLeft: '0.5rem',
                        padding: '0.5rem 1rem',
                        borderRadius: '0.25rem',
                        border: 'none',
                        background: '#e94560',
                        color: '#fff',
                        cursor: 'pointer'
                    }}
                >
                    Send
                </button>
            </form>
        </div>
    );
}

export default Chat;