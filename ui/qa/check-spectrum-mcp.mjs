import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const require=createRequire(import.meta.url);
const spectrumRequire=createRequire(require.resolve('@spectrumui/mcp/package.json'));
const {Client}=await import(pathToFileURL(spectrumRequire.resolve('@modelcontextprotocol/sdk/client/index.js')).href);
const {StdioClientTransport}=await import(pathToFileURL(spectrumRequire.resolve('@modelcontextprotocol/sdk/client/stdio.js')).href);
const client=new Client({name:'guidefold-spectrum-qa',version:'1.0.0'});
const transport=new StdioClientTransport({command:process.execPath,args:[require.resolve('@spectrumui/mcp')],cwd:resolve('.'),stderr:'pipe'});
const result={configuredPackage:require('@spectrumui/mcp/package.json').version};
try {
  await client.connect(transport);
  result.tools=(await client.listTools()).tools.map(tool=>tool.name);
  for(const [name,args] of [['list_components',{}],['list_categories',{}],['search_components',{query:'beam',limit:5}],['get_component',{name:'beam-search'}]]){
    const response=await client.callTool({name,arguments:args},undefined,{timeout:20000});
    if(response.isError)throw new Error(name+': '+response.content.filter(c=>c.type==='text').map(c=>c.text).join(' '));
    const data=JSON.parse(response.content.find(c=>c.type==='text').text);
    result[name]=name==='list_components'?{total:data.total}:name==='list_categories'?{count:data.categories.length}:name==='search_components'?data.results.map(x=>x.name):{name:data.name};
  }
  result.installation='Real shadcn CLI install verified separately; no writes from this MCP diagnostic.';
  console.log(JSON.stringify(result,null,2));
} finally {await client.close();}
