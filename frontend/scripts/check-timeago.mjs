import assert from 'node:assert/strict';
import { timeAgo } from '../src/lib/utils.ts';

// run: node --experimental-strip-types scripts/check-timeago.mjs
const now = Date.now();
assert.equal(timeAgo(null), 'never');
assert.equal(timeAgo(new Date(now - 10_000).toISOString()), 'just now');
assert.equal(timeAgo(new Date(now - 5 * 60_000).toISOString()), '5m ago');
assert.equal(timeAgo(new Date(now - 3 * 3_600_000).toISOString()), '3h ago');
assert.equal(timeAgo(new Date(now - 2 * 86_400_000).toISOString()), '2d ago');
console.log('timeAgo ok');
