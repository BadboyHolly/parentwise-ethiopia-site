// node qa-tests/checkout_message_check.js
// The Telegram message a parent sends must carry the "how did you hear" answer, and the form must refuse to continue without it.
const fs = require('fs'), vm = require('vm'), path = require('path'), assert = require('assert');
const html = fs.readFileSync(path.join(__dirname, '..', 'site-preview', 'order.html'), 'utf8');
const start = html.indexOf('const buildMessage=()=>[');
const end = html.indexOf(".join('\\n');", start) + ".join('\\n');".length;
assert.ok(start > 0 && end > start, 'buildMessage not found');
const build = (data, method) => vm.runInNewContext(html.slice(start, end) + ';buildMessage()', { data, method });
const base = { name: 'Almaz Tesfaye', phone: '0912345678' };
const friend = build({ ...base, heard: 'friend' }, 'telebirr');
assert.match(friend, /ከየት ሰሙ: ጓደኛ ወይም ቤተሰብ \[friend\]/);
assert.match(friend, /ስም: Almaz Tesfaye/); assert.match(friend, /Amount: 1,500 ETB/);
for (const [key, label] of [['ad', 'ማስታወቂያ'], ['telegram', 'ቴሌግራም'], ['other', 'ሌላ']]) assert.ok(build({ ...base, heard: key }, 'bank').includes(`ከየት ሰሙ: ${label} [${key}]`), key);
assert.match(build({ ...base, heard: '' }, 'bank'), /ከየት ሰሙ: — \[-\]/);     // never a crash on a missing answer
const options = [...html.matchAll(/<select id="heard-from"[^>]*required>([\s\S]*?)<\/select>/g)];
assert.strictEqual(options.length, 1, 'one required question');
assert.deepStrictEqual([...options[0][1].matchAll(/value="([^"]*)"/g)].map((m) => m[1]), ['', 'ad', 'telegram', 'friend', 'other']);
assert.ok(/if\(!\$\('heard-from'\)\.value\)\{error\(/.test(html), 'the form refuses to continue without an answer');
console.log('ok  checkout message carries the answer; the question is required with the four fixed options');
