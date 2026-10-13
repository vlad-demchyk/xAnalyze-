// Deterministic PerformanceObserver delivery through the shipped web-vitals build.
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
global.window = global;
global.document = {visibilityState: 'visible', readyState: 'complete',
  prerendering: false, addEventListener() {}, removeEventListener() {}};
global.addEventListener = global.removeEventListener = () => {};
global.requestAnimationFrame = cb => setTimeout(cb, 0);
global.requestIdleCallback = cb => setTimeout(cb, 0);
global.innerWidth = 1440; global.innerHeight = 900; global.devicePixelRatio = 1;
global.performance = {now: () => 10000, timeOrigin: 0, interactionCount: 0,
  getEntriesByType: t => t === 'navigation' ? [{activationStart: 0, type: 'navigate',
    responseStart: 0, domContentLoadedEventStart: 100, loadEventStart: 150}] : []};
const observers = [];
global.PerformanceObserver = class {
  static supportedEntryTypes = ['paint', 'layout-shift', 'largest-contentful-paint', 'event', 'first-input'];
  constructor(cb) {this.cb = cb; observers.push(this);}
  observe(opts) {
    this.type = opts.type;
    if (this.type === 'paint') queueMicrotask(() => this.emit([
      {name: 'first-contentful-paint', entryType: 'paint', startTime: 100, duration: 0}]));
  }
  emit(entries) {this.cb({getEntries: () => entries});}
  takeRecords() {return [];}
  disconnect() {}
};
vm.runInThisContext(input.bootstrap);
setTimeout(() => {
  for (const observer of observers.filter(o => o.type === 'layout-shift')) {
    observer.emit(input.shifts.map(e => ({entryType: 'layout-shift', duration: 0,
      sources: [], hadRecentInput: false, ...e})));
  }
  setTimeout(() => {
    vm.runInThisContext('(function(result){' + input.snapshot + '})(globalThis.result)', {
      filename: 'snapshot.js',
    });
  }, 0);
}, 5);
// A separate context binding for the probe; no implementation of CLS here.
global.result = {};
setTimeout(() => process.stdout.write(JSON.stringify(global.result)), 30);
