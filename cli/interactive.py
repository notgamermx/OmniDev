#!/usr/bin/env python3
"""OmniDev CLI Interactive Mode."""

import asyncio
import json
import sys
from datetime import datetime, timezone


class InteractiveShell:
    """Interactive shell for OmniDev CLI."""

    def __init__(self, api_client):
        self.api = api_client
        self.context = {}
        self.commands = self._register_commands()

    def _register_commands(self):
        """Register available commands."""
        return {
            '/help': self.cmd_help,
            '/exit': self.cmd_exit,
            '/clear': self.cmd_clear,
            '/agents': self.cmd_agents,
            '/tasks': self.cmd_tasks,
            '/memory': self.cmd_memory,
            '/files': self.cmd_files,
            '/run': self.cmd_run,
        }

    async def cmd_help(self, args):
        """Show help."""
        print("""
OmniDev Interactive Shell
Commands:
  /help       - Show this help
  /exit       - Exit shell
  /clear      - Clear screen
  /agents     - Show/create agents
  /tasks      - Show/create tasks
  /memory     - Memory operations
  /files      - File operations
  /run        - Run a task
  /think      - AI think tool
  help        - Show help
        """)

    async def cmd_exit(self, args):
        """Exit shell."""
        print("Goodbye!")
        sys.exit(0)

    async def cmd_clear(self, args):
        """Clear screen."""
        print("\033[2J\033[H", end="")

    async def cmd_agents(self, args):
        """List/create agents."""
        if args.get('create'):
            # Create new agent
            result = await self.api.create_agent({
                'name': args.get('name', f'agent-{datetime.now().strftime("%H%M%S")}'),
                'model': args.get('model', 'llama3.1:8b'),
                'provider': args.get('provider', 'ollama')
            })
            print(json.dumps(result, indent=2))
        else:
            # List agents
            result = await self.api.list_agents()
            print(json.dumps(result, indent=2))

    async def cmd_tasks(self, args):
        """List/create tasks."""
        if args.get('create'):
            result = await self.api.create_task({
                'agent_id': args.get('agent_id', 1),
                'title': args.get('title', 'Interactive Task'),
                'description': args.get('description', '')
            })
            print(json.dumps(result, indent=2))
        else:
            result = await self.api.list_tasks()
            for task in result.get('tasks', []):
                print(f"  [{task['id']}] {task['title']} - {task['status']}")

    async def cmd_memory(self, args):
        """Memory operations."""
        action = args.get('action', 'list')

        if action == 'set':
            result = await self.api.set_session_memory({
                'key': args.get('key'),
                'value': args.get('value')
            })
            print(f"Set: {result.get('key')} = {result.get('value')}")
        elif action == 'get':
            result = await self.api.get_session_memory(args.get('key'))
            print(json.dumps(result, indent=2))
        elif action == 'list':
            result = await self.api.listSessionMemories()
            print(json.dumps(result, indent=2))

    async def cmd_files(self, args):
        """File operations."""
        action = args.get('action', 'list')

        if action == 'read':
            result = await self.api.readFile(args.get('path'))
            print(result.get('content', ''))
        elif action == 'write':
            result = await self.api.writeFile(args.get('path'), args.get('content'))
            print(f"Wrote to {result.get('path')}")
        elif action == 'list':
            result = await self.api.listFiles(args.get('path', '.'))
            for item in result.get('items', []):
                icon = '📁' if item.get('isDirectory') else '📄'
                print(f"  {icon} {item.get('name')}")

    async def cmd_run(self, args):
        """Run a task."""
        task_id = args.get('task_id')
        if not task_id:
            print("Usage: /run task_id=<id>")
            return

        result = await self.api.executeTask(task_id, args.get('project_root', '.'))
        print(json.dumps(result, indent=2))

    async def cmd_think(self, args):
        """Use the think tool."""
        thought = args.get('thought')
        if not thought:
            print("Usage: think thought=<reasoning>")
            return

        result = await self.api.request('/api/v1/tools/think', 'POST', {
            'thought': thought
        })
        print(json.dumps(result, indent=2))

    async def run(self):
        """Run the interactive shell."""
        print("OmniDev Interactive Shell v1.0")
        print("Type /help for commands, /exit to quit\n")

        while True:
            try:
                # Get prompt with context
                prompt = self._get_prompt()
                line = input(prompt)

                # Execute line
                await self.execute(line)

            except EOFError:
                break
            except KeyboardInterrupt:
                print()
            except Exception as e:
                print(f"Error: {e}")

    def _get_prompt(self):
        """Get the command prompt."""
        return "omnidev> "

    async def execute(self, line):
        """Execute a line of input."""
        line = line.strip()
        if not line:
            return

        # Check for command
        if line.startswith('/'):
            parts = line.split(' ', 1)
            cmd = parts[0].lower()
            args_str = parts[1] if len(parts) > 1 else ''

            # Parse arguments
            args = self._parse_args(args_str)

            if cmd in self.commands:
                await self.commands[cmd](args)
            else:
                print(f"Unknown command: {cmd}")
            return

        # Otherwise treat as a task/operation
        result = await self.api.create_task({
            'agent_id': self.context.get('agent_id', 1),
            'title': f'Interactive: {line[:50]}',
            'description': line
        })

        # Execute and show result
        task_result = await self.api.executeTask(result['id'])
        print(task_result.get('result', 'No result'))

    def _parse_args(self, args_str):
        """Parse command arguments."""
        args = {}
        if not args_str:
            return args

        # Simple key=value parsing
        for part in args_str.split():
            if '=' in part:
                key, value = part.split('=', 1)
                args[key.strip()] = value.strip()

        return args


# Enhanced API client for CLI
class CLIClient:
    """CLI-compatible API client."""

    def __init__(self, host='localhost', port=8000):
        self.host = host
        self.port = port

    async def request(self, path, method='GET', body=None):
        """Make HTTP request."""
        import httpx
        url = f"http://{self.host}:{self.port}{path}"

        try:
            async with httpx.AsyncClient() as client:
                if method == 'GET':
                    response = await client.get(url)
                elif method == 'POST':
                    response = await client.post(url, json=body)
                elif method == 'DELETE':
                    response = await client.delete(url)
                else:
                    response = await client.request(method, url, json=body)

                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {'error': str(e)}

    # Convenience methods
    async def list_agents(self):
        return await self.request('/api/v1/agents/')

    async def create_agent(self, data):
        return await self.request('/api/v1/agents/', 'POST', data)

    async def get_agent(self, agent_id):
        return await self.request(f'/api/v1/agents/{agent_id}')

    async def delete_agent(self, agent_id):
        return await self.request(f'/api/v1/agents/{agent_id}', 'DELETE')

    async def list_tasks(self):
        return await self.request('/api/v1/tasks/')

    async def create_task(self, data):
        return await self.request('/api/v1/tasks/', 'POST', data)

    async def executeTask(self, task_id, project_root='.'):
        return await self.request(f'/api/v1/tasks/{task_id}/execute', 'POST', {'project_root': project_root})

    async def listSessionMemories(self):
        return await self.request('/api/v1/memory/session')

    async def set_session_memory(self, data):
        return await self.request('/api/v1/memory/session/', 'POST', data)

    async def get_session_memory(self, key):
        return await self.request(f'/api/v1/memory/session/{key}')

    async def readFile(self, path):
        return await self.request('/api/v1/tools/read_file', 'POST', {'path': path})

    async def writeFile(self, path, content):
        return await self.request('/api/v1/tools/write_file', 'POST', {'path': path, 'content': content})

    async def listFiles(self, path='.'):
        return await self.request('/api/v1/tools/list_files', 'POST', {'path': path})


async def main():
    """Run interactive shell."""
    import argparse
    parser = argparse.ArgumentParser(description='OmniDev Interactive Shell')
    parser.add_argument('--host', default='localhost', help='API host')
    parser.add_argument('--port', type=int, default=8000, help='API port')
    args = parser.parse_args()

    client = CLIClient(args.host, args.port)
    shell = InteractiveShell(client)
    await shell.run()


if __name__ == '__main__':
    asyncio.run(main())