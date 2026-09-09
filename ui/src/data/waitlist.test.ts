import {afterEach,describe,it,expect,vi} from 'vitest';
import {submitWaitlist} from './waitlist';
afterEach(()=>vi.unstubAllGlobals());
describe('waitlist transport',()=>{
 it('posts without credentials and requires the response contract',async()=>{const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({schema_version:'1.0',request_id:'test',data:{status:'pending'}}),{status:202}));vi.stubGlobal('fetch',fetch);await submitWaitlist('join',{email:'a@example.test',consent:true});expect(fetch).toHaveBeenCalledWith('/api/v1/waitlist',expect.objectContaining({method:'POST',credentials:'omit',body:'{"email":"a@example.test","consent":true}'}));});
 it.each([{}, {schema_version:'1.0',request_id:'test',data:{status:'confirmed'}}])('rejects malformed or wrong-state success',async body=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify(body))));await expect(submitWaitlist('join',{})).rejects.toMatchObject({kind:'unavailable'});});
 it.each([[429,'limited'],[400,'invalid'],[410,'expired'],[500,'unavailable']])('maps HTTP %s without exposing response bodies',async(status,kind)=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('private',{status:Number(status)})));await expect(submitWaitlist('join',{})).rejects.toMatchObject({kind});});
});
