// Run with node --test tests/test_portfolio.cjs (no dependencies).
const {test,beforeEach}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const elements=new Map();
const document={getElementById(id){if(!elements.has(id)) elements.set(id,{value:id==='period'?'recent':id==='portfolio-period'?'recent':'diff',addEventListener(){}});return elements.get(id)}};
const context=vm.createContext({document,URL,console,fetch:()=>new Promise(()=>{})});
vm.runInContext(fs.readFileSync('docs/index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1],context);
const run=code=>vm.runInContext(code,context);
beforeEach(()=>run(`loadHoldings(['730956','737036','408333'].map(id=>({url:'https://snkrdunk.com/apparels/'+id,quantity:'2'})))`));
test('latest two prices per card; unmatched cards excluded from both comparison totals',()=>{
 run(`build([{url:'a',source_date:'2026-09-05',price:'150'},{url:'a',source_date:'2026-08-01',price:'100'},{url:'b',source_date:'2026-09-06',price:'80'},{url:'c',source_date:'2026-09-02',price:'40'},{url:'c',source_date:'2026-09-01',price:'50'}]);renderPortfolio()`);
 assert.deepEqual(JSON.parse(run('JSON.stringify(portfolioTotals(cards))')),{total:270,count:3,current:190,previous:150,comparable:2,diff:40,pct:40/150});
 assert.match(elements.get('portfolio-basis').textContent,/比較価格のない 1枚/);
 assert.equal(run("compare(cards[0].rows,'6months')"),null);
 const before=elements.get('portfolio-total').textContent;
 for(const period of ['recent','7','30','3months','6months']) for(const metric of ['diff','pct']) {elements.get('period').value=period;elements.get('metric').value=metric;run('render()');assert.equal(elements.get('portfolio-total').textContent,before);}
});
test('empty, one price, zero baseline, decreases and invalid prices',()=>{
 for(const [prices,diff,pct] of [[[],null,null],[[10],null,null],[[0,10],10,null],[[100,80],-20,-.2],[[100,100],0,0]]){
 const result=context.portfolioTotals([{rows:prices.map(price=>({price}))}]);assert.equal(result.diff,diff);assert.equal(result.pct,pct);
 }
 run(`build([{url:'a',source_date:'2026-09-01',price:''},{url:'a',source_date:'2026-09-02',price:'NaN'}]);renderPortfolio()`);
 assert.equal(elements.get('portfolio-total').textContent,'¥0');
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

const card=(url,entries)=>({url,rows:entries.map(([date,price])=>({date,price}))});
test('calendar comparisons use exact date or nearest earlier date and the same owned copies',()=>{
 const items=[
 card('https://snkrdunk.com/apparels/730956', [['2026-06-06',50],['2026-08-07',80],['2026-08-30',100],['2026-09-06',150]]),
 card('b', [['2026-06-01',20],['2026-08-01',40],['2026-08-29',60],['2026-09-04',90]]),
 card('https://snkrdunk.com/apparels/737036', [['2026-09-01',30],['2026-09-06',40]])
 ];
 for(const [period,previous] of [['7',240],['30',200],['3months',120]]){
  const s=context.portfolioTotals(items,period,'2026-09-06');
  assert.deepEqual(JSON.parse(JSON.stringify(s)),{total:470,count:5,current:390,previous,comparable:3,diff:390-previous,pct:(390-previous)/previous});
 }
 const recent=context.portfolioTotals(items,'recent','2026-09-06');
 assert.equal(recent.comparable,5);assert.equal(recent.previous,320);
});
test('calendar month subtraction clamps month end and Japan date crosses UTC midnight',()=>{
 for(const [today,expected] of [['2026-05-31','2026-02-28'],['2024-05-31','2024-02-29'],['2026-01-31','2025-10-31'],['2026-09-06','2026-06-06']])
  assert.equal(context.portfolioTarget('3months',today),expected);
 assert.equal(context.portfolioTarget('7','2026-01-03'),'2025-12-27');
 assert.equal(context.portfolioTarget('6months','2024-08-31'),'2024-02-29');
 assert.equal(context.portfolioTarget('6months','2026-03-31'),'2025-09-30');
});
test('calendar periods: no eligible history, zero baseline, stale latest and decreases',()=>{
 assert.equal(context.portfolioTotals([card('a',[['2026-09-01',100]])],'7','2026-09-06').comparable,0);
 const zero=context.portfolioTotals([card('a',[['2026-08-30',0],['2026-09-06',10]])],'7','2026-09-06');
 assert.equal(zero.diff,10);assert.equal(zero.pct,null);
 const stale=context.portfolioTotals([card('a',[['2026-08-01',100]])],'7','2026-09-06');
 assert.equal(stale.diff,null);assert.equal(stale.comparable,0);
 const down=context.portfolioTotals([card('a',[['2026-08-30',100],['2026-09-06',80]])],'7','2026-09-06');
 assert.equal(down.diff,-20);assert.equal(down.pct,-.2);
});
test('portfolio period changes do not change ranking controls or rendered cards',()=>{
 const before=elements.get('list').innerHTML;
 for(const period of ['recent','7','30','3months','6months']){
  elements.get('portfolio-period').value=period;run('renderPortfolio()');
  assert.equal(elements.get('list').innerHTML,before);
  assert.match(elements.get('portfolio-basis').textContent,/比較対象 \d+枚／全\d+枚/);
 }
});

test('six months uses each latest date, falls back only earlier and excludes missing history',()=>{
 const items=[card('a',[['2026-02-28',100],['2026-03-01',999],['2026-08-31',150]]),card('b',[['2026-02-27',50],['2026-08-30',80]]),card('c',[['2026-03-01',90],['2026-08-31',110]])];
 const s=context.portfolioTotals(items,'6months');
 assert.equal(s.current,230);assert.equal(s.previous,150);assert.equal(s.comparable,2);assert.equal(s.diff,80);
 assert.equal(context.compare(items[0].rows,'6months').base,'2026-02-28');
 assert.equal(context.compare(items[1].rows,'6months').base,'2026-02-27');
 assert.equal(context.compare(items[2].rows,'6months'),null);
 assert.equal(context.compare(items[0].rows,'recent').old,999);
});

test('zero is excluded from every total, restore works and ranking filter is independent',()=>{
 run(`loadHoldings([{url:'https://snkrdunk.com/apparels/1',quantity:'0'},{url:'https://snkrdunk.com/apparels/2',quantity:'3'}]);build([
 {url:'https://snkrdunk.com/apparels/1',name:'Unowned',source_date:'2025-01-01',price:'100'},
 {url:'https://snkrdunk.com/apparels/1',name:'Unowned',source_date:'2026-09-01',price:'200'},
 {url:'https://snkrdunk.com/apparels/2',name:'Owned',source_date:'2025-01-01',price:'10'},
 {url:'https://snkrdunk.com/apparels/2',name:'Owned',source_date:'2026-09-01',price:'20'}])`);
 for(const period of ['recent','7','30','3months','6months']){
  const s=context.portfolioTotals(run('cards'),period);
  assert.equal(s.total,60);assert.equal(s.previous,30);assert.equal(s.diff,30);assert.equal(s.count,3);
 }
 elements.get('ownership-filter').value='all';run('render()');assert.match(elements.get('list').innerHTML,/未所持（0枚）/);
 elements.get('ownership-filter').value='owned';run('render()');assert.doesNotMatch(elements.get('list').innerHTML,/Unowned/);
 run(`holdings['https://snkrdunk.com/apparels/1']=1`);assert.equal(run('portfolioTotals(cards).total'),260);
 run(`holdings['https://snkrdunk.com/apparels/1']=0;holdings['https://snkrdunk.com/apparels/2']=0;renderPortfolio()`);
 assert.equal(elements.get('portfolio-total').textContent,'¥0');assert.equal(run('portfolioTotals(cards).diff'),null);
});
test('quantity issue link uses absolute target count and validates input',()=>{
 for(const quantity of [0,1,9999]){
  const url=new URL(context.quantityRequest('https://snkrdunk.com/apparels/1',quantity));
  assert.equal(url.searchParams.get('quantity'),String(quantity));assert.equal(url.searchParams.get('template'),'update-quantity.yml');
 }
 for(const value of [-1,1.5,10000,'', '1e2']) assert.throws(()=>context.quantityRequest('https://snkrdunk.com/apparels/1',value));
 assert.throws(()=>run(`loadHoldings([{url:'https://snkrdunk.com/apparels/1',quantity:'-1'}])`));
});
