/**
 * OmniDev Desktop - Terminal Panel Component
 */

import React, { useState, useEffect, useRef } from 'react';

function TerminalPanel() {
    const [sessionId] = useState(`terminal-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
    const [output, setOutput] = useState('');
    const [input, setInput] = useState('');
    const [history, setHistory] = useState([]);
    const [historyIndex, setHistoryIndex] = useState(-1);
    const outputRef = useRef(null);

    useEffect(() => {
        // Initialize terminal
        initTerminal();

        // Listen for terminal output (would be via IPC in real app)
        const handler = (event, data) => {
            if (data.sessionId === sessionId) {
                setOutput(prev => prev + data.data);
            }
        };

        if (window.electronAPI?.on) {
            window.electronAPI.on.terminalOutput(handler);
        }

        return () => {
            // Cleanup
            window.electronAPI?.on?.removeAllListeners?.();
        };
    }, [sessionId]);

    async function initTerminal() {
        try {
            await window.electronAPI?.terminal?.create?.(sessionId);
            setOutput('Terminal initialized...\n');
        } catch (error) {
            setOutput(`Failed to initialize terminal: ${error.message}\n`);
        }
    }

    function scrollToBottom() {
        outputRef.current?.scrollIntoView({ behavior: 'smooth' });
    }

    useEffect(() => {
        scrollToBottom();
    }, [output]);

    async function handleInput(e) {
        e.preventDefault();
        if (!input.trim()) return;

        // Add to history
        setHistory(prev => [...prev, input]);
        setHistoryIndex(-1);

        // Send to terminal
        try {
            await window.electronAPI?.terminal?.input?.(sessionId, input + '\n');
            setOutput(prev => prev + `> ${input}\n`);
            setInput('');
        } catch (error) {
            setOutput(prev => prev + `Error: ${error.message}\n`);
        }
    }

    function handleKeyDown(e) {
        if (e.key === 'ArrowUp') {
            if (historyIndex < history.length - 1) {
                setHistoryIndex(prev => prev + 1);
                setInput(history[historyIndex + 1]);
            }
        } else if (e.key === 'ArrowDown') {
            if (historyIndex > -1) {
                setHistoryIndex(prev => prev - 1);
                setInput(historyIndex === 0 ? '' : history[historyIndex - 1]);
            }
        }
    }

    async function handleClear() {
        setOutput('');
        setHistory([]);
        setHistoryIndex(-1);
    }

    return (
        <div className="terminal-container">
            <div className="terminal-output" ref={outputRef}>
                {output || 'Type a command and press Enter...'}
            </div>
            <div className="terminal-input">
                <span>{'> '}</span>
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleInput}
                    onKeyPress={(e) => handleKeyDown(e)}
                    placeholder="Type command..."
                />
            </div>
            <div style={{ padding: '0.5rem', backgroundColor: '#0f3460', display: 'flex', gap: '0.5rem' }}>
                <button onClick={handleClear} style={{ padding: '0.25rem 0.5rem' }}>Clear</button>
                <button onClick={initTerminal} style={{ padding: '0.25rem 0.5rem' }}>Reset</button>
            </div>
        </div>
    );
}

export default TerminalPanel;