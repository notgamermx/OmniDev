/**
 * OmniDev Desktop - Code Editor Component
 */

import React, { useState, useEffect } from 'react';

function CodeEditor({ file, fileOperation }) {
    const [content, setContent] = useState('');
    const [isEditing, setIsEditing] = useState(false);
    const [filePath, setFilePath] = useState(file?.path || '');

    useEffect(() => {
        if (file) {
            loadFile(file.path);
            setFilePath(file.path);
        }
    }, [file]);

    async function loadFile(path) {
        try {
            const result = await fileOperation('read', path);
            setContent(result.content || '');
        } catch (error) {
            console.error('Failed to load file:', error);
            setContent(`Error loading file: ${error.message}`);
        }
    }

    async function handleSave() {
        try {
            await fileOperation('write', filePath, content);
            alert('File saved successfully');
        } catch (error) {
            console.error('Failed to save file:', error);
            alert(`Error saving file: ${error.message}`);
        }
    }

    function getLanguage(filename) {
        const ext = filename.split('.').pop()?.toLowerCase();
        const languages = {
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'py': 'python',
            'java': 'java',
            'c': 'c',
            'cpp': 'cpp',
            'h': 'c',
            'hpp': 'cpp',
            'html': 'html',
            'css': 'css',
            'json': 'json',
            'md': 'markdown',
            'yaml': 'yaml',
            'yml': 'yaml',
            'xml': 'xml',
            'sh': 'bash',
            'bash': 'bash'
        };
        return languages[ext] || 'text';
    }

    return (
        <div className="editor-container">
            <div className="file-info">
                {file?.path || 'Untitled'} | Language: {file ? getLanguage(file.path) : 'text'}
            </div>
            <div style={{ display: 'flex', height: 'calc(100% - 40px)' }}>
                <textarea
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    style={{
                        flex: 1,
                        padding: '1rem',
                        border: 'none',
                        backgroundColor: '#0d1117',
                        color: '#fff',
                        fontFamily: 'monospace',
                        fontSize: '14px',
                        resize: 'none',
                        outline: 'none'
                    }}
                    spellCheck={false}
                />
            </div>
            <div style={{ padding: '0.5rem 1rem', backgroundColor: '#0f3460', display: 'flex', gap: '0.5rem' }}>
                <button onClick={() => setIsEditing(!isEditing)} style={{ padding: '0.25rem 0.5rem' }}>
                    {isEditing ? 'View' : 'Edit'}
                </button>
                <button onClick={handleSave} style={{ padding: '0.25rem 0.5rem', background: '#e94560' }}>
                    Save
                </button>
                <button onClick={() => loadFile(file?.path)} style={{ padding: '0.25rem 0.5rem' }}>
                    Refresh
                </button>
            </div>
        </div>
    );
}

export default CodeEditor;