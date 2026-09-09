import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import {fileURLToPath, URL} from 'node:url';
/** Dev proxy: the management API and the retrieval contract run on 127.0.0.1:8765. */
const api={target:'http://127.0.0.1:8765',changeOrigin:false,secure:false};
export default defineConfig({plugins:[react(),tailwindcss()],resolve:{alias:{'@':fileURLToPath(new URL('./src',import.meta.url))}},server:{host:'127.0.0.1',port:4331,strictPort:true,proxy:{'/api':api,'/v1':api}},preview:{host:'127.0.0.1',port:4331,strictPort:true}});
