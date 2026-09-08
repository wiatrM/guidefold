import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
/** Dev proxy: the management API and the retrieval contract run on 127.0.0.1:8765. */
const api={target:'http://127.0.0.1:8765',changeOrigin:false,secure:false};
export default defineConfig({plugins:[react()],server:{host:'127.0.0.1',port:4331,strictPort:true,proxy:{'/api':api,'/v1':api}},preview:{host:'127.0.0.1',port:4331,strictPort:true}});
