export function lineDiff(source:string,candidate:string):string{
 if(source===candidate)return 'No text changes';
 const a=source.split('\n'),b=candidate.split('\n');let first=0,lastA=a.length,lastB=b.length;
 while(first<Math.min(a.length,b.length)&&a[first]===b[first])first++;
 while(lastA>first&&lastB>first&&a[lastA-1]===b[lastB-1]){lastA--;lastB--;}
 const start=Math.max(0,first-2),endA=Math.min(a.length,lastA+2),endB=Math.min(b.length,lastB+2);
 return ['@@ -'+(start+1)+','+(endA-start)+' +'+(start+1)+','+(endB-start)+' @@',
 ...a.slice(start,first).map(x=>'  '+x),...a.slice(first,lastA).map(x=>'− '+x),
 ...b.slice(first,lastB).map(x=>'+ '+x),...a.slice(lastA,endA).map(x=>'  '+x)].join('\n');
}
