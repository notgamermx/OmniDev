/**
 * OmniDev Desktop - File Explorer Component
 */

import React, { useState, useEffect } from 'react';

function FileExplorer({ selectedFile, onFileSelect, fileOperation }) {
    const [files, setFiles] = useState([]);
    const [currentPath, setCurrentPath] = useState('.');
    const [isLoading, setIsLoading] = useState(false);
    const [expandedPaths, setExpandedPaths] = useState(new Set());

    useEffect(() => {
        loadFiles('.');
    }, []);

    async function loadFiles(path) {
        setIsLoading(true);
        try {
            const result = await fileOperation('list', path);
            setFiles(result.items || []);
            setCurrentPath(result.path || path);
        } catch (error) {
            console.error('Failed to load files:', error);
            setFiles([]);
        } finally {
            setIsLoading(false);
        }
    }

    function handleFileClick(item) {
        if (item.isDirectory) {
            const newPath = `${currentPath}/${item.name}`;
            if (expandedPaths.has(newPath)) {
                setExpandedPaths(prev => {
                    const next = new Set(prev);
                    next.delete(newPath);
                    return next;
                });
            } else {
                setExpandedPaths(prev => new Set(prev).add(newPath));
            }
            loadFiles(newPath);
        } else {
            onFileSelect(item);
        }
    }

    function handleDoubleClick(item) {
        if (!item.isDirectory) {
            onFileSelect(item);
        }
    }

    async function handleDelete(item) {
        if (window.confirm(`Delete ${item.name}?`)) {
            // File deletion would require backend support
            console.log('Delete:', item.path);
        }
    }

    return (
        <div className="file-explorer">
            <div className="file-tree">
                {isLoading ? (
                    <div className="file-node">Loading...</div>
                ) : (
                    files.map(item => (
                        <div
                            key={item.path}
                            className={`file-node ${selectedFile?.path === item.path ? 'selected' : ''}`}
                            onClick={() => handleFileClick(item)}
                            onDoubleClick={() => handleDoubleClick(item)}
                            style={{ paddingLeft: `${(item.path.match(/\//g) || []).length * 1.5}rem` }}
                        >
                            <span style={{ marginRight: '0.5rem' }}>
                                {item.isDirectory ? (expandedPaths.has(item.path) ? '📂' : '📁') : '📄'}
                            </span>
                            <span>{item.name}</span>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

export default FileExplorer;