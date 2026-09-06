// Run with node --test tests/test_portfolio.cjs (no dependencies).
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const elements=new Map();
const document={getElementById(id){if(!elements.has(id)) elements.set(id,{value:id==='period'?'1':'diff',addEventListener(){}});return elements.get(id)}};
const context=vm.createContext({document,URL,console,fetch:()=>new Promise(()=>{})});
vm.runInContext(fs.readFileSync('docs/index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1],context);
const run=code=>vm.runInContext(code,context);
test('latest two prices per card; unmatched cards excluded from both comparison totals',()=>{
 run(`build([{url:'a',source_date:'2026-09-05',price:'150'},{url:'a',source_date:'2026-08-01',price:'100'},{url:'b',source_date:'2026-09-06',price:'80'},{url:'c',source_date:'2026-09-02',price:'40'},{url:'c',source_date:'2026-09-01',price:'50'}]);renderPortfolio()`);
 assert.deepEqual(JSON.parse(run('JSON.stringify(portfolioTotals(cards))')),{total:270,count:3,current:190,previous:150,comparable:2,diff:40,pct:40/150});
 assert.match(elements.get('portfolio-basis').textContent,/前回価格のない 1枚/);
 assert.equal(run('compare(cards[0].rows,1)'),null);
 const before=elements.get('portfolio-total').textContent;
 for(const period of ['1','7','30']) for(const metric of ['diff','pct']) {elements.get('period').value=period;elements.get('metric').value=metric;run('render()');assert.equal(elements.get('portfolio-total').textContent,before);}
});
test('empty, one price, zero baseline, decreases and invalid prices',()=>{
 for(const [prices,diff,pct] of [[[],null,null],[[10],null,null],[[0,10],10,null],[[100,80],-20,-.2],[[100,100],0,0]]){
 const result=context.portfolioTotals([{rows:prices.map(price=>({price}))}]);assert.equal(result.diff,diff);assert.equal(result.pct,pct);
 }
 run(`build([{url:'a',source_date:'2026-09-01',price:''},{url:'a',source_date:'2026-09-02',price:'NaN'}]);renderPortfolio()`);
 assert.equal(elements.get('portfolio-total').textContent,'—');
});
test('real data renders and keeps card addition URL validation',()=>{
 context.raw=fs.readFileSync('docs/history.csv','utf8');run('build(csvParse(raw));renderPortfolio();render()');
 assert.ok(run('portfolioTotals(cards).total')>0);
 assert.equal(run("normalizedCardUrl('https://snkrdunk.com/apparels/91156?x=1')"),'https://snkrdunk.com/apparels/91156');
 console.log(elements.get('portfolio-total').textContent,elements.get('portfolio-change').textContent,elements.get('portfolio-basis').textContent);
});

test('owned copies weight both comparison totals; new cards default to one',()=>{
 const s=context.portfolioTotals([
 {url:'https://snkrdunk.com/apparels/730956',rows:[{price:100},{price:150}]},
 {url:'https://snkrdunk.com/apparels/737036',rows:[{price:80},{price:60}]},
 {url:'https://snkrdunk.com/apparels/408333',rows:[{price:50}]},
 {url:'new',rows:[{price:10},{price:20}]}
 ]);
 assert.deepEqual(JSON.parse(JSON.stringify(s)),{total:540,count:7,current:440,previous:370,comparable:5,diff:70,pct:70/370});
});
