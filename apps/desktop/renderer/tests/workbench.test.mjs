import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
const vite = await createServer({ optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true }, appType: 'custom' });
const { default: ModelPicker } = await vite.ssrLoadModule('/src/ModelPicker.jsx');
const api = await vite.ssrLoadModule('/src/services/api.js');
test.after(() => vite.close());
const store = () => ({ getItem: () => null });
globalThis.localStorage = store(); globalThis.sessionStorage = store();
globalThis.location = { protocol: 'http:', hostname: 'localhost' };
test('model picker only lists configured providers', () => {
 const html=renderToStaticMarkup(React.createElement(ModelPicker, {providers:[{name:'groq', configured:true, display_name:'Groq'},{name:'openai',configured:false,display_name:'OpenAI'}], provider:'groq', model:'', onProvider(){}, onModel(){}}));
 assert.match(html,/Groq/); assert.doesNotMatch(html,/OpenAI|setup needed/);
});
test('engine addresses accept copied API links and reject embedded secrets', () => {
 assert.equal(api.normalizeEngineUrl(' http://localhost:8000/api/v1/ '),'http://localhost:8000');
 assert.equal(api.normalizeEngineUrl('https://example.com/proxy/app/'),'https://example.com/proxy');
 for(const value of ['file:///tmp','https://user:key@example.com','https://example.com?key=secret']) assert.throws(()=>api.normalizeEngineUrl(value));
});
test('proxy HTML and network failures produce actionable errors', async () => {
 globalThis.fetch=async()=>new Response('<html>error</html>', {status:502,headers:{'content-type':'text/html'}});
 await assert.rejects(()=>api.request('/workspace'),/without JSON/);
 globalThis.fetch=async()=>{throw new TypeError('Failed to fetch')};
 await assert.rejects(()=>api.request('/workspace'),/Cannot reach the engine/);
});
test('writes are not retried and authentication errors explain the token', async()=>{
 let calls=0; globalThis.fetch=async()=>{calls++;return new Response(JSON.stringify({detail:'Unauthorized'}), {status:401,headers:{'content-type':'application/json'}})};
 await assert.rejects(()=>api.request('/file','PUT',{path:'x',content:'y'}),/API token/);assert.equal(calls,1);
});
test('chat rejects a proxy page returned as a successful response', async()=>{
 globalThis.fetch=async()=>new Response('<html>login</html>', {headers:{'content-type':'text/html'}});
 await assert.rejects(()=>api.streamChat({},()=>{}),/did not return a chat stream/);
});
