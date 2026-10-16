// Run only with WorkBuddy's bundled Electron in Node mode.
// Decode the current access token in memory; output only numeric package metrics.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const https = require('node:https');
let stage = 'runtime';
async function main() {
  const mainDir = path.resolve(path.dirname(process.execPath), '../Resources/app.asar/main');
  let crypto;
  if (fs.existsSync(path.join(mainDir, 'process-cpu-sampler.js'))) {
    crypto = require(path.join(mainDir, 'process-cpu-sampler.js'));
    crypto.init_dist();
  } else {
    // Newer official Rolldown bundle: initialize before reading lazy exports.
    const bundle = require(path.join(mainDir, 'app-lifetime-job.js'));
    if (typeof bundle.L !== 'function') throw Error();
    bundle.L();
    crypto = {AtRestCrypto: bundle.I,
      normalizeAtRestBuildKeyCapabilities: bundle.U,
      parseSupportedEnvelope: bundle.W};
  }
  for (const name of ['AtRestCrypto', 'normalizeAtRestBuildKeyCapabilities', 'parseSupportedEnvelope']) {
    if (typeof crypto[name] !== 'function') throw Error();
  }
  stage = 'login';
  const authPath = path.join(os.homedir(), 'Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info');
  if (fs.existsSync(authPath + '.logged-out')) throw Error();
  const session = JSON.parse(fs.readFileSync(authPath, 'utf8'));
  if (session.account?.enterpriseId) { stage = 'enterprise'; throw Error(); }
  const wrapped = session.auth?.accessToken;
  if (wrapped?.$wbEncrypted !== 1 || wrapped.scheme || typeof wrapped.envelope !== 'string') throw Error();
  stage = 'decode';
  const capabilities = crypto.normalizeAtRestBuildKeyCapabilities(
    process._linkedBinding('electron_browser_workbuddy_storage').loggerGet());
  if (capabilities.symmetric.status !== 'ready') {
    // The bundled normalizer uses 'available' in some releases.
    if (!capabilities.symmetric.value) throw Error();
  }
  const key = capabilities.symmetric.value;
  let cipher, plain, token;
  try {
    cipher = new crypto.AtRestCrypto(key);
    plain = cipher.open(crypto.parseSupportedEnvelope(Buffer.from(wrapped.envelope, 'base64')), {framing:'field'});
    token = plain.toString('utf8');
  } finally {
    plain?.fill(0); cipher?.dispose(); key?.key.fill(0);
  }
  if (!token || /[\r\n]/.test(token)) throw Error();
  stage = 'network';
  const headers = {
    'Authorization': 'Bearer ' + token, 'X-User-Id': session.account?.uid || '',
    'Content-Type': 'application/json', 'Accept':'application/json',
    'User-Agent':'WaveshareUsageMonitor/1.1', 'X-Product':'WorkBuddy',
    'X-IDE-Type':'WorkBuddy', 'X-IDE-Name':'WorkBuddy'
  };
  if (session.auth.domain) headers['X-Domain'] = session.auth.domain;
  const result = await new Promise((resolve,reject) => {
    const req = https.request('https://copilot.tencent.com/billing/meter/get-user-resource-summary',
      {method:'POST', headers}, res => {
        if (res.statusCode !== 200) { stage = 'http-' + res.statusCode; res.resume(); reject(Error()); return; }
        let body = '', size = 0;
        res.on('data', chunk => { size += chunk.length; if(size>1048576) {req.destroy();reject(Error());} else body += chunk; });
        res.on('error', reject);
        res.on('end', () => {try {resolve(JSON.parse(body));} catch {reject(Error());}});
      });
    req.on('error', reject); req.setTimeout(20000, () => req.destroy(Error())); req.end('{}');
  });
  token = undefined; delete headers.Authorization;
  stage = 'response';
  if (result.code !== 0 || !Array.isArray(result.data?.Packages)) throw Error();
  const fields = ['CycleTotalCapacity','CycleRemainCapacity','CycleUsedCapacity'];
  const packages = result.data.Packages.map(p => Object.fromEntries(fields.map(k => {
    const raw=p[k], n=Number(raw);
    if(!['number','string'].includes(typeof raw) || raw === '' || !Number.isFinite(n) || n<0) throw Error();
    return [k,n];
  })));
  process.stdout.write(JSON.stringify({Packages:packages}));
}
main().catch(() => {process.stderr.write('WorkBuddy reader failed ('+stage+')\n');process.exitCode=1;});
