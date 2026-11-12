const fs = require('fs');
const corpus = require('@stdlib/datasets-spam-assassin');
const data = corpus();
fs.writeFileSync('spamassassin.jsonl', data.map(d => JSON.stringify({ id: d.id, group: d.group, text: d.text })).join('\n') + '\n');
const count = {};
data.forEach(d => { count[d.group] = (count[d.group] || 0) + 1; });
console.log(count);
