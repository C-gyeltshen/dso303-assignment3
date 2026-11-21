// k6 load test: students start an exam and autosave until the test ends, then submit.
//
//   k6 run -e BASE_URL=https://dxxxx.cloudfront.net -e EXAM_IDS=3,4,5,6,7,8 exam-peak.js
//
// Parameters (all optional):
//   STUDENTS       number of concurrent students (VUs)            default 3000
//   START_WINDOW   seconds over which they all start the exam     default 300 (brief: 3,000 within 5 min)
//   SAVE_INTERVAL  seconds between autosaves                      default 30
//   HOLD           seconds to keep autosaving after the ramp      default 600
// A laptop that cannot run 3,000 VUs can generate the SAME request rate with fewer students:
//   STUDENTS=1000 SAVE_INTERVAL=10  -> 100 autosaves/s, identical to 3,000 students every 30 s.
// Step test to find the knee: run again with SAVE_INTERVAL=5 (200/s) and 2.5 (400/s).
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import exec from 'k6/execution';

const BASE = __ENV.BASE_URL;
const STUDENTS = Number(__ENV.STUDENTS || 3000);
const START_WINDOW = Number(__ENV.START_WINDOW || 300);
const SAVE_INTERVAL = Number(__ENV.SAVE_INTERVAL || 30);
const HOLD = Number(__ENV.HOLD || 600);
const EXAMS = (__ENV.EXAM_IDS || '').split(',').filter(Boolean).map(Number);
const tokens = new SharedArray('tokens', () => JSON.parse(open('./tokens.json')));

const saveOk = new Rate('autosave_ok');
const startLatency = new Trend('exam_start_ms', true);
const saveLatency = new Trend('autosave_ms', true);
const throttled = new Counter('http_429_or_503');

export const options = {
  scenarios: {
    exam: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: `${START_WINDOW}s`, target: STUDENTS },
        { duration: `${HOLD}s`, target: STUDENTS },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],      // SLO: < 1 % errors
    autosave_ms: ['p(95)<1000'],         // SLO: p95 autosave < 1 s
    exam_start_ms: ['p(95)<2000'],       // SLO: p95 exam start < 2 s
    autosave_ok: ['rate>0.99'],
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
};

export function setup() {
  if (!BASE || !EXAMS.length) throw new Error('BASE_URL and EXAM_IDS are required');
  if (tokens.length * EXAMS.length < STUDENTS) {
    throw new Error(`need users x exams >= STUDENTS (${tokens.length} x ${EXAMS.length} < ${STUDENTS})`);
  }
}

export default function () {
  // Each VU is one (student, exam) pair, so attempts never collide.
  const vu = exec.vu.idInTest - 1;
  const token = tokens[vu % tokens.length];
  const examId = EXAMS[Math.floor(vu / tokens.length) % EXAMS.length];
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const start = http.post(`${BASE}/api/exams/${examId}/start`, null, { headers, tags: { name: 'start' } });
  startLatency.add(start.timings.duration);
  if (start.status === 429 || start.status === 503) throttled.add(1);
  if (!check(start, { 'start 200': (r) => r.status === 200 })) { sleep(5); return; }
  const { attempt, questions } = start.json();

  let seq = attempt.client_seq || 0;
  const answers = {};
  const endAt = Date.now() + (HOLD + START_WINDOW) * 1000;
  sleep(Math.random() * SAVE_INTERVAL); // students don't all save on the same second
  while (Date.now() < endAt && exec.scenario.progress < 0.99) {
    const q = questions[Math.floor(Math.random() * questions.length)];
    answers[q.id] = Math.floor(Math.random() * 4);
    seq += 1;
    const r = http.put(`${BASE}/api/attempts/${attempt.id}/answers`,
      JSON.stringify({ answers, clientSeq: seq }), { headers, tags: { name: 'autosave' } });
    saveLatency.add(r.timings.duration);
    if (r.status === 429 || r.status === 503) throttled.add(1);
    saveOk.add(r.status === 200);
    sleep(SAVE_INTERVAL);
  }
  http.post(`${BASE}/api/attempts/${attempt.id}/submit`, null, { headers, tags: { name: 'submit' } });
}
